$(function(){
    $('.btn-small-bank').click(function() {
        $('.btn-small-bank').removeClass('active');
        $(this).addClass('active');
    });
    
    $('#banks_main_search_form').submit(function() {
        $(this).find('input[value=],input[type=submit]').attr('disabled', 'disabled');
        $(this).attr('action', '/' + $('.btn-small-bank.active').attr('stype')+ '/result.html');
    });
});

