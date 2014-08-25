function indexLayout() {
	var navX = $('section nav').offset().left;
	var navY = $('section nav').offset().top;
	$('section nav').css({
		'position':'fixed',
		'left': navX,
		'top': navY
	});
		//改变窗口大小时，现获取section的位置，重新定位
	$(window).resize(function() {
		var sectionX = $('section').offset().left;
		$('section nav').css('left',sectionX);
		if($(window).height() <= 650) {
			$('section nav').css({
				'height':'350px',
			});
		} else {
			$('section nav').css({
				'height':'450px',
			});
		}
	});
}

function baseLayout() {
	$('aside').css({
		'right': '0',
		'top': '60px'
	});
}

function shortPageFooter() {
	var height = $(window).height() - 50;
	$('footer').css({
		'position':'fixed',
		'top':height
	});
	$(window).resize(function() {
		var height = $(window).height() - 50;
		$('footer').css({
			'position':'fixed',
			'top':height
		});
	});
}

/*function footContent() {
	$('.group').hover(
		function() {
			$('.foot-content').css('line-height','25px');
			$('.members').show();
		}, 
		function() {
			$('.foot-content').css('line-height','50px');
			$('.members').hide();
		}
	);
}
*/

/*function showMessage() {
	$('aside').animate({width:"600px"},500);
}

function hideMessage() {
	$('aside').animate({width:"0px"},500);
}*/

function scrollMore() {
	$('.scrollMore').hover(function() {
		$(this).css('overflow','auto');
	}, function() {
		$(this).css('overflow','hidden');
	});
}

$(function() {
	baseLayout();
	scrollMore()
})