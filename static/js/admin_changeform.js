$(function () {
    $('.model-ad.change-form .field-address p').each(function() {
        var address = $(this).text();
        $(this).append(' &nbsp; <a href="https://yandex.ru/maps/?text=' + address + '" class="button">а де це?</a>');
    });
});