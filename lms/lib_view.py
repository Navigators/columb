# -*-coding:utf-8 -*-
import datetime
import json
import re
import time
import urllib2

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core import serializers
from django.db.models import Q
from django.http.response import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.utils import simplejson, timezone
import django.utils
from django.views.decorators.csrf import csrf_exempt

from columb.settings import MEDIA_ROOT
from lms.login_view import is_login_lib
from lms.models import Books, Librarians, BookCate, BookType, Copies, CopyState, \
    Readers, LoanList, Company, Department, BooksBuy, BooksApply, \
    BooksArchive, ReaderCate


#################################入库模块##################################
def lib_index(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    else:
        return render(request, 'lms/lib/index.html', {'username':request.user.username})
 
def lib_putaway(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    else:
        return render(request, 'lms/lib/addBook.html', {'username':request.user.username})

def lib_buybook(request):
    book_apply = BooksApply.objects.all()
    book_buy = BooksBuy.objects.all()
    book_archive = BooksArchive.objects.all()
    return render(request, 'lms/lib/buyBook.html', {'username':request.user.username,
                                                    'bookapply':book_apply,
                                                    'bookbuy':book_buy,
                                                    'bookarchive':book_archive,
                                                    }
                  )
    
def lib_reader_info(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    if request.GET.get('json_id'):
        reader = Readers.objects.get(id=request.GET.get("json_id"))
        user = User.objects.get(username=reader.username)
        user.set_password(user.username) 
        user.save()
        data = {'status':'success'}
        return HttpResponse(json.dumps(data, sort_keys=True, ensure_ascii=False), content_type='json')
    
    if request.GET.get('json_username'):
        if Readers.objects.filter(username=request.GET.get("json_username")):
            data = {}
            user_info = serializers.serialize('json', User.objects.filter(username=request.GET.get("json_username")), ensure_ascii=False)
            user = json.loads(user_info)
            reader_info = serializers.serialize('json', Readers.objects.filter(username=request.GET.get("json_username")), ensure_ascii=False, use_natural_keys=True)
            reader = json.loads(reader_info)
            data["user"] = user
            data["reader"] = reader
            return HttpResponse(json.dumps(data, sort_keys=True, ensure_ascii=False), content_type='json')
    
    readers = Readers.objects.all()
    return render(request, 'lms/lib/readerInfo.html', {'username':request.user.username, 'readers':readers, })

def lib_retrieve(request):
    # 验证用户登录
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    # 返回json数据
    if request.GET.get('json_isbn'):
        proxy= "http://10.167.251.83:8080"
        opener=urllib2.build_opener(urllib2.ProxyHandler({'http':proxy})).close()
        urllib2.install_opener(opener)
        data = urllib2.urlopen("http://10.167.129.109:3000/ISBNService/" + request.GET.get('json_isbn')).read()
        return HttpResponse(data, content_type='json')
    
    if request.GET.get('json_others'):
        proxy= "http://10.167.251.83:8080"
        opener=urllib2.build_opener(urllib2.ProxyHandler({'http':proxy}))
        urllib2.install_opener(opener) 
        others = urllib2.urlopen("http://api.douban.com/v2/book/isbn/" + request.GET.get('json_others') + "?fields=image,summary").read()
        return HttpResponse(others, content_type='json')
    
    # 正常加载
    isbn_string = request.POST['isbn']
    pattern = re.compile(u"^\d{10}$|^\d{13}$")
    if not pattern.search(isbn_string):
        return render(request, 'lms/lib/addBook.html', {'username':request.user.username})
    else:
        book = Books.objects.filter(isbn=isbn_string)
        if not book:
            return render(request, 'lms/lib/addBook-new.html', {
                                                                'username':request.user.username,
                                                                'isbn':isbn_string,
                                                                'types':BookType.objects.all(),
                                                                'date':time.strftime('%Y-%m-%d', time.localtime(time.time()))
                                                                }
                          )
        else:
            copy_list = Copies.objects.filter(book__isbn=isbn_string)
            return render(request, 'lms/lib/addBook-copy.html', {
                                                                 'username':request.user.username,
                                                                 'copy_list':copy_list,
                                                                 'isbn':isbn_string,
                                                                 }
                          )       

def lib_add_copies(request):
    # 验证用户登录
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    # Ajax继续添加副本，并选择数量
    if request.GET.get('json_isbn'):
        lib = Librarians.objects.get(username=request.user.username)
        book = Books.objects.filter(isbn=request.GET.get('json_isbn'))[0]
        #
        if request.GET.get('json_add_num'):
            for i in range(int(request.GET.get('json_add_num'))):
                book.copies_set.create(
                                       barcode=get_barcode_format(book.isbn, book.copies_set.all().order_by('-reg_date_time')),
                                       state=CopyState.objects.get(name="可借"),
                                       operator=lib,
                                       )
                book.total_count += 1
                book.save()
        #
        if request.GET.get('json_code'):
            copy = Copies.objects.filter(barcode=request.GET.get('json_code'))[0]
            if request.GET.get('json_status'):
                copy.state = CopyState.objects.filter(name=request.GET.get('json_status'))[0]
                copy.operator = lib
                copy.save()
            else:
                copy.delete()
          
        data = serializers.serialize('json', Copies.objects.filter(book__isbn=request.GET.get('json_isbn')), ensure_ascii=False, use_natural_keys=True)
        return HttpResponse(data, content_type='json')
    
    # 入库及第一个副本
    isbn_string = request.POST['isbn']
    if not Books.objects.filter(isbn=isbn_string):
        lib = Librarians.objects.get(username=request.user.username)
        pic_path=save_image(request.POST['bookimage'],isbn_string)
        lib.books_set.create(
                                isbn=isbn_string,
                                name=request.POST['bookName'],
                                input_code=request.POST['inputCode'],
                                author=request.POST['author'],
                                book_type=BookType.objects.get(name=request.POST['bookType']),
                                cate=BookCate.objects.get(code=request.POST['categoryID']),
                                publisher=request.POST['publisher'],
                                publish_date=get_publishdate_form(request.POST['publishDate']),
                                publish_addr=request.POST['publishAddr'],
                                price=request.POST['bookPrice'],
                                content_intro=request.POST['contentInfo'],
                                memo=request.POST['memo'],
                                pic_location =pic_path,
                            )
        book = Books.objects.get(isbn=isbn_string)
        book.copies_set.create(
                                barcode=get_barcode_format(book.isbn, book.copies_set.all().order_by('-reg_date_time')),
                                state=CopyState.objects.get(name="可借"),
                                operator=lib,
                                )
        book.total_count += 1
        book.save()
        
        # 将准备购入BooksToBuy对应的表象删除，并添加至BooksToArchive表中
#         if BooksBuy.objects.filter(isbn=isbn_string):
#             book_buy=BooksBuy.objects.get(isbn=isbn_string)
#             lib.bookstoarchive_set.create(
#                                           name=book_buy.name,
#                                           author=book_buy.author,
#                                           publisher=book_buy.publihser,
#                                           isbn=book_buy.isbn,
#                                           price=book_buy.price,
#                                           state="已购入",
#                                           requester=book_buy.requester,
#                                           )
#             book_buy.delete()

    # 无论是查看or保存并继续添加副本，都会有form表单
    isbn = Books.objects.get(isbn=request.POST['isbn']).isbn
    copy_list = Copies.objects.filter(book__isbn=request.POST['isbn'])
    return render(request, 'lms/lib/addBook-copy.html', {'username':request.user.username, 'copy_list':copy_list, 'isbn':isbn, })
    
def lib_get_book_list(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    # Ajaxs搜索图书
    if request.GET.get('json_isbn'):
        isbn_string = request.GET.get('json_isbn')
        pattern = re.compile(u"^\d{10}$|^\d{13}$")
        if pattern.search(isbn_string):
            data = serializers.serialize('json', Books.objects.filter(isbn=request.GET.get('json_isbn')), ensure_ascii=False, use_natural_keys=True)
            return HttpResponse(data, content_type='json')
    
    return render(request, 'lms/lib/booksInfo.html', {'username':request.user.username, 'book_list':Books.objects.all()})

def lib_get_book_info(request, isbn):
    book_info = Books.objects.get(isbn=int(isbn))
    return render(request, 'lms/lib/addBook-new.html', {'username':request.user.username, 'book':book_info})

def save_image(url, isbn):
    # 保存文件时候注意类型要匹配，如要保存的图片为jpg，则打开的文件的名称必须是jpg格式，否则会产生无效图片
    proxy= "http://10.167.251.83:8080"
    opener=urllib2.build_opener(urllib2.ProxyHandler({'http':proxy}))
    urllib2.install_opener(opener) 
    data = urllib2.urlopen(url).read()  
    f = file(MEDIA_ROOT + "/" + isbn + ".jpg", "wb")
    f.write(data)  
    f.close()
    return str(MEDIA_ROOT + "/" + isbn + ".jpg")

def get_barcode_format(isbn, copies):
    if not copies:
        return isbn + "001"
    sub_str = copies[0].barcode
    last_id = int(sub_str[-3:])
    if str(last_id + 1).__len__() == 1:
        return isbn + "00" + str(last_id + 1)
    elif str(last_id + 1).__len__() == 2:
        return isbn + "0" + str(last_id + 1)
    elif str(last_id + 1).__len__() == 3:
        return isbn + str(last_id + 1)

def get_publishdate_form(date_string):
    if date_string.find(".") < 0:
        return django.utils.datetime_safe.datetime.strptime(date_string, "%Y")
    else:
        return django.utils.datetime_safe.datetime.strptime(date_string, "%Y.%m")
      
#################################借还模块##################################

@csrf_exempt
def lib_return_borrow(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    if request.method == 'POST':
        if request.POST['funno'] == '201':
            return lib_borrow_getcopy(request)
        if request.POST['funno'] == '202':
            return lib_borrow_getreader(request)
        if request.POST['funno'] == '203':
            return lib_borrow(request)
        if request.POST['funno'] == '204':
            return lib_return(request)
        if request.POST['funno'] == '205':
            return lib_reloan(request)
    else:
        return render(request, 'lms/lib/returnBorrow.html', {'username':request.user.username, })
def lib_borrow_getcopy(request):
    mbarcode = request.POST['text']
    r_dict = {}
    if Copies.objects.filter(barcode=mbarcode):
        mcopy = Copies.objects.get(barcode=mbarcode)
        r_dict['state'] = 'getcopy success'
        r_dict['copy'] = copy_to_dict(mcopy)
    else:
        r_dict['state'] = 'getcopy fail'
    r_json = simplejson.dumps(r_dict, ensure_ascii=False)
    return HttpResponse(r_json)
def copy_to_dict(copy):
    copydict = {}
    copydict['copyid'] = copy.id
    copydict['barcode'] = copy.barcode
    copydict['name'] = copy.book.name
    copydict['isbn'] = copy.book.isbn
    copydict['author'] = copy.book.author
    copydict['cate'] = copy.book.cate.name
    return copydict
    
def lib_borrow_getreader(request):
    card = request.POST['text']
    r_dict = {}
    if Readers.objects.filter(username=card):
        mreader = Readers.objects.get(username=card)
        r_dict['state'] = 'getreader success'
        r_dict['reader'] = reader_to_dict(mreader)
    else:
        r_dict['state'] = 'getreader fail'
    r_json = simplejson.dumps(r_dict, ensure_ascii=False)
    return HttpResponse(r_json)
def reader_to_dict(reader):
    readerdict = {}
    readerdict['readerid'] = reader.id
    readerdict['username'] = reader.username
    readerdict['name'] = reader.name
    readerdict['cate'] = reader.cate.name
    readerdict['corp'] = reader.corp.name
    readerdict['dept'] = reader.dept.name
    return readerdict

def loan_to_dict(loan):
    loandict = {}
    loandict['loandatetime'] = loan.loan_date_time.strftime("%Y-%m-%d %H:%M:%S")
    loandict['bookname'] = loan.copy.book.name
    loandict['booktype'] = loan.copy.book.book_type.name
    loandict['barcode'] = loan.copy.barcode
    loandict['catecode'] = loan.copy.book.cate.code
    loandict['readername'] = loan.reader.name
    loandict['username'] = loan.reader.username
    loandict['usercate'] = loan.reader.cate.name
    loandict['dept'] = loan.reader.dept.name
    loandict['shouldreturndate'] = loan.should_return_date.strftime("%Y-%m-%d")
    loandict['reloantimes'] = loan.reloan_times
    loandict['operator'] = loan.loan_operator.name 
    if loan.return_operator:
        loandict['returnoperator'] = loan.return_operator.name 
    else:
        loandict['returnoperator'] = "" 
    return loandict


def lib_borrow(request):
    copyid = int(request.POST['copyid'])
    readerid = int(request.POST['readerid'])
    # check if reader exists
    if Readers.objects.filter(pk=readerid):
        mreader = Readers.objects.get(pk=readerid)
    else:
        return HttpResponse('{"state":"reader not found"}') 
    # check if copy exists
    if Copies.objects.filter(pk=copyid):
        mcopy = Copies.objects.get(pk=copyid)
    else:
        return HttpResponse('{"state":"copy not found"}') 
    # check if copy can be borrowed
    if LoanList.objects.filter(copy=mcopy, is_return=False):
        return HttpResponse('{"state":"copy is borrowed"}') 
    if mcopy.state.name != '可借':
        return HttpResponse('{"state":"book is '+mcopy.book.book_type.name+'borrowed"}') 
    # check if reader can borrow japanese book
    if not mreader.cate.loan_books_jp:
        return HttpResponse('{"state":"cant borrow japanese books"}') 
    # check if reader has book that didnt return in time 
    loan_list_set = LoanList.objects.filter(reader=mreader, is_return=False)
    if loan_list_set:
        for ml in loan_list_set:
            if ml.should_return_date < timezone.now().date():
                return HttpResponse('{"state":"book beyond date"}') 
    # modify next line when user module added!
    mloan_operator = Librarians.objects.get(username=request.user.username)
    mis_return = False
    mpraise = False
    if LoanList.objects.filter(copy=mcopy, is_return=False):
        return HttpResponse('{"state":"loan record not found"}') 
    else:
        mlimit_days = mreader.cate.limit_days
        mshould_return_date = timezone.now() + datetime.timedelta(days=mlimit_days)
        LoanList.objects.create(copy=mcopy, reader=mreader, should_return_date=mshould_return_date, is_return=mis_return, loan_operator=mloan_operator, praise=mpraise)
        mbook = mcopy.book
        mbook.loan_count += 1
        mbook.save()
        r_dict = {}
        r_dict['state'] = 'borrow success'
        loan_list_set = LoanList.objects.filter(reader=mreader, is_return=False)
        loan_list = []
        if loan_list_set:
            for ml in loan_list_set:
                loan_list.append(loan_to_dict(ml))
        r_dict['loanlist'] = loan_list
        r_json = simplejson.dumps(r_dict, ensure_ascii=False)
        return HttpResponse(r_json)

def lib_return(request):
    copyid = int(request.POST['copyid'])
    if Copies.objects.filter(pk=copyid):
        mcopy = Copies.objects.get(pk=copyid)
    else:
        return HttpResponse('{"state":"copy not found"}') 
    if LoanList.objects.filter(copy=mcopy, is_return=False):
        mloan = LoanList.objects.get(copy=mcopy, is_return=False)
    else:
        return HttpResponse('{"state":"loan record not found"}') 
    # modify next line when user module added!
    mreturn_operator = Librarians.objects.get(username=request.user.username)
    mreader = mloan.reader
    if mloan.is_return == False:
        mloan.is_return = True
        mloan.return_operator = mreturn_operator
        mloan.fact_return_date_time = timezone.now()
        mloan.save()
        mbook = mcopy.book
        mbook.loan_count -= 1
        mbook.save()
        r_dict = {}
        r_dict['state'] = 'return success'
        loan_list_set = LoanList.objects.filter(reader=mreader, is_return=False)
        loan_list = []
        if loan_list_set:
            for ml in loan_list_set:
                loan_list.append(loan_to_dict(ml))
        r_dict['loanlist'] = loan_list
        r_json = simplejson.dumps(r_dict, ensure_ascii=False)
        return HttpResponse(r_json)

def lib_reloan(request):
    copyid = int(request.POST['copyid'])
    # check if copy exists
    if Copies.objects.filter(pk=copyid):
        mcopy = Copies.objects.get(pk=copyid)
    else:
        return HttpResponse('{"state":"copy not found"}') 
    # check if loan record exists
    if LoanList.objects.filter(copy=mcopy, is_return=False):
        mloan = LoanList.objects.get(copy=mcopy, is_return=False)
    else:
        return HttpResponse('{"state":"loan record not found"}') 
    mreader = mloan.reader
    # check if reader has book that didnt return in time 
    loan_list_set = LoanList.objects.filter(reader=mreader, is_return=False)
    if loan_list_set:
        for ml in loan_list_set:
            if timezone.now().date() > ml.should_return_date:
                return HttpResponse('{"state":"book beyond date"}') 

    # check reloan times
    if mloan.reloan_times < mreader.cate.reloan_times:
        mloan.reloan_times += 1 
    else:
        return HttpResponse('{"state":"cannot reloan any more"}') 
    # check if on five days before deadline
    if timezone.now().date() < mloan.should_return_date - datetime.timedelta(days=5):
        return HttpResponse('{"state":"cannot reloan yet"}') 
    # modify next line when user module added!
    mloan.reloan_operator = Librarians.objects.get(username=request.user.username)
    mloan.should_return_date = mloan.should_return_date + datetime.timedelta(days=mreader.cate.reloan_days)
    mloan.save()
    r_dict = {}
    r_dict['state'] = 'reloan success'
    loan_list_set = LoanList.objects.filter(reader=mreader, is_return=False)
    loan_list = []
    if loan_list_set:
        for ml in loan_list_set:
            loan_list.append(loan_to_dict(ml))
    r_dict['loanlist'] = loan_list
    r_json = simplejson.dumps(r_dict, ensure_ascii=False)
    return HttpResponse(r_json)

def lib_borrow_permission(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    if request.method == 'POST':
        if request.POST['funno'] == "1":
            return lib_borrow_permission_add(request)
        if request.POST['funno'] == "2":
            return lib_borrow_permission_update(request)
        if request.POST['funno'] == "3":
            return lib_borrow_permission_delete(request)
    return render(request, 'lms/lib/borrowPermission.html', {'username':request.user.username,'readercate':ReaderCate.objects.all() })

def lib_borrow_permission_add(request):
    print("pa")
    _name = request.POST['readerCategory']
    _limit_books_count = int(request.POST['borrowBooks'])
    _limit_days = int(request.POST['borrowDays'])
    _reloan_times = int(request.POST['renewalTimes'])
    _reloan_days = int(request.POST['renewalDays'])
    _loan_books_jp = False
    if  request.POST.has_key('japBooks'):
        _loan_books_jp = True
    ReaderCate.objects.create( name = _name, limit_books_count = _limit_books_count, limit_days = _limit_days, reloan_times = _reloan_times, reloan_days = _reloan_days, loan_books_jp = _loan_books_jp)
    reader_json = serializers.serialize('json', ReaderCate.objects.all())
    return HttpResponse(reader_json)

def lib_borrow_permission_update(request):
    _id = int(request.POST['id'])
    if ReaderCate.objects.filter(pk=_id):
        _reader_cate = ReaderCate.objects.get(pk=_id)
    else:
        return HttpResponseRedirect('/lib/borrowpermission/')
    _reader_cate.name = request.POST['readerCategory']
    _reader_cate.limit_books_count = int(request.POST['borrowBooks'])
    _reader_cate.limit_days = int(request.POST['borrowDays'])
    _reader_cate.reloan_times = int(request.POST['renewalTimes'])
    _reader_cate.reloan_days = int(request.POST['renewalDays'])
    if  request.POST.has_key('japBooks'):
        _reader_cate.loan_books_jp = True
    else:
        _reader_cate.loan_books_jp = False
    _reader_cate.save()
    reader_json = serializers.serialize('json', ReaderCate.objects.all())
    return HttpResponse(reader_json)

@csrf_exempt
def lib_borrow_permission_delete(request):
    _id = int(request.POST['id'])
    if ReaderCate.objects.filter(pk=_id):
        _reader_cate = ReaderCate.objects.get(pk=_id)
        _reader_cate.delete()
    return HttpResponse('{"state":"delete ok"}') 


def lib_borrow_record(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    if request.method != 'POST':
        return render(request, 'lms/lib/borrowRecord.html', {'username':request.user.username })
    _query_json = request.POST['queryjson']
    _query_list = json.loads(_query_json)
    _item_dict = {}
    _item_dict['1'] = 'loan_date_time'
    _item_dict['2'] = 'copy__book__name'
    _item_dict['3'] = 'copy__book__input_code'
    _item_dict['4'] = 'copy__book_type'
    _item_dict['5'] = 'copy__barcode'
    _item_dict['6'] = 'copy__cate__name'
    _item_dict['7'] = 'reader__name'
    _item_dict['8'] = 'reader__username'
    _item_dict['9'] = 'reader__cate__name'
    _item_dict['10'] = 'reader__dept__name'
    _item_dict['11'] = 'should_return_date'
    _item_dict['12'] = 'reloan_times'
    _item_dict['13'] = 'loan_operator'
    _item_dict['14'] = 'return_operator'
    
    _condition_dict = {}
    _condition_dict['l'] = '__lt' 
    _condition_dict['le'] = '__lte' 
    _condition_dict['g'] = '__gt' 
    _condition_dict['ge'] = '__gte' 
    _condition_dict['e'] = '__exact' 
    _condition_dict['contain'] = '__contains' 

    kwargs = {}
    orargs = [None,None,None,None,None,None,None,None,None,None,None,None,None,None]
    args = []
    for qobj in _query_list:
        if qobj[u'logic']== u'and':
            if qobj[u'item'] == '1': 
                datelist = []
                datelist = qobj[u'value'].split('-')
                tdate = datetime.date(int(datelist[0]),int(datelist[1]),int(datelist[2]))
                if qobj[u'condition'] == 'e':
                    kwargs[_item_dict[qobj[u'item']]+'__range'] = (datetime.datetime.combine(tdate, datetime.time.min),
                                                        datetime.datetime.combine(tdate, datetime.time.max))
                if qobj[u'condition'] == 'le':
                    kwargs[_item_dict[qobj[u'item']]+'__lt'] =  datetime.datetime.combine(tdate, datetime.time.max)
                if qobj[u'condition'] == 'ge':
                    kwargs[_item_dict[qobj[u'item']]+'__gt'] = qobj[u'value'] 

            else:
                kwargs[_item_dict[qobj[u'item']]+_condition_dict[qobj[u'condition']]] = qobj[u'value'] 
        if qobj[u'logic']== u'or':
            tdict = {}
            if qobj[u'item'] == '1': 
                datelist = []
                datelist = qobj[u'value'].split('-')
                tdate = datetime.date(int(datelist[0]),int(datelist[1]),int(datelist[2]))
                if qobj[u'condition'] == 'e':
                    tdict[_item_dict[qobj[u'item']]+'__range'] = (datetime.datetime.combine(tdate, datetime.time.min),
                                                        datetime.datetime.combine(tdate, datetime.time.max))
                if qobj[u'condition'] == 'le':
                    tdict[_item_dict[qobj[u'item']]+'__lt'] =  datetime.datetime.combine(tdate, datetime.time.max)
                if qobj[u'condition'] == 'ge':
                    tdict[_item_dict[qobj[u'item']]+'__gt'] = qobj[u'value'] 
            else:
                tdict[_item_dict[qobj[u'item']]+_condition_dict[qobj[u'condition']]] = qobj[u'value']
            print(qobj[u'value'])
            if orargs[int(qobj[u'item'])] is None:
                orargs[int(qobj[u'item'])] = Q(**tdict) 
            else:
                orargs[int(qobj[u'item'])] |= Q(**tdict)
    for targs in orargs:
        if targs:
            args.append(targs)
    _loan_list = LoanList.objects.filter(*args,**kwargs)
    _loan_list_json = serializers.serialize('json', _loan_list)
    return HttpResponse(_loan_list_json) 


def lib_overdue(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    _start_date = datetime.date(1970,1,1)
    _end_date = timezone.now().date()
    _overdue_list=LoanList.objects.filter(is_return = False,should_return_date__range = (_start_date,_end_date)) 
    return render(request, 'lms/lib/overdueRecord.html', {'username':request.user.username,'overdue_list':_overdue_list })
	
#################################系统设置模块##################################

def lib_meta_data(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    if request.GET.get("json_item"):
        if request.GET.get("json_name") and request.GET.get("json_id"):
            return lib_meta_modify(request)
        elif request.GET.get("json_name"):
            return lib_meta_add(request)
        elif request.GET.get("json_id"):
            return lib_meta_delete(request)
    else:
        return render(request, 'lms/lib/metaData.html', {
                                                         'username':request.user.username,
                                                         'companies':Company.objects.all(),
                                                         'departments':Department.objects.all(),
                                                         'book_types':BookType.objects.all(),
                                                         'copy_states':CopyState.objects.all(),
                                                         }
                      )
    
def lib_manage_password(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    
    if request.method == "POST":
        old_pd = request.POST['oldPassword']
        new_pd1 = request.POST['newPassword1']
        new_pd2 = request.POST['newPassword2']
        if old_pd and new_pd1 and new_pd2:
            user = authenticate(username=request.user.username, password=old_pd)
            if user is not None and user.is_active:  
                if new_pd1 == new_pd2:
                    user.set_password(new_pd1) 
                    user.save()
                    change_pd_error = ""
                    return HttpResponseRedirect('/index/')
                else:
                    change_pd_error = "Enter the new password twice inconsistent!"
                    return render(request, 'lms/lib/password.html', {'username':request.user.username, 'change_pd_error':change_pd_error, })
            else:
                change_pd_error = "Enter the old password is incorrect!"
                return render(request, 'lms/lib/password.html', {'username':request.user.username, 'change_pd_error':change_pd_error, })
        else:
            change_pd_error = "Please complete the form!"
            return render(request, 'lms/lib/password.html', {'username':request.user.username, 'change_pd_error':change_pd_error, })

    return render(request, 'lms/lib/password.html', {'username':request.user.username, })
    
def lib_push_message(request):
    if not is_login_lib(request):
        return HttpResponseRedirect('/index/')
    else:
        return render(request, 'lms/lib/push.html', {'username':request.user.username})

def lib_meta_add(request):
    item = request.GET.get("json_item")
    name_string = request.GET.get("json_name") 
    if item == '0':
        Company.objects.create(name=name_string)
        data = serializers.serialize('json', Company.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "1":
        Department.objects.create(name=name_string)
        data = serializers.serialize('json', Department.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "2":
        BookType.objects.create(name=name_string)
        data = serializers.serialize('json', BookType.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "3":
        CopyState.objects.create(name=name_string)
        data = serializers.serialize('json', CopyState.objects.all(), ensure_ascii=False, use_natural_keys=True)
    else:
        data = ""
    return HttpResponse(data, content_type='json')
def lib_meta_modify(request):
    item = request.GET.get("json_item")
    id_string = request.GET.get("json_id") 
    name_string = request.GET.get("json_name") 
    if item == '0':
        company = Company.objects.get(id=id_string)
        company.name = name_string
        company.save()
        data = serializers.serialize('json', Company.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "1":
        department = Department.objects.get(id=id_string)
        department.name = name_string
        department.save()
        data = serializers.serialize('json', Department.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "2":
        booktype = BookType.objects.get(id=id_string)
        booktype.name = name_string
        booktype.save()
        data = serializers.serialize('json', BookType.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "3":
        copystate = CopyState.objects.get(id=id_string)
        copystate.name = name_string
        copystate.save()
        data = serializers.serialize('json', CopyState.objects.all(), ensure_ascii=False, use_natural_keys=True)
    else:
        data = ""
    return HttpResponse(data, content_type='json')

def lib_meta_delete(request):
    item = request.GET.get("json_item")
    id_string = request.GET.get("json_id") 
    if item == '0':
        company = Company.objects.get(id=id_string)
        company.delete()
        data = serializers.serialize('json', Company.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "1":
        department = Department.objects.get(id=id_string)
        department.delete()
        data = serializers.serialize('json', Department.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "2":
        bookType = BookType.objects.get(id=id_string)
        bookType.delete()
        data = serializers.serialize('json', BookType.objects.all(), ensure_ascii=False, use_natural_keys=True)
    elif item == "3":
        copystate = CopyState.objects.get(id=id_string)
        copystate.delete()
        data = serializers.serialize('json', CopyState.objects.all(), ensure_ascii=False, use_natural_keys=True)
    else:
        data = ""
    return HttpResponse(data, content_type='json')