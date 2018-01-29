$('#callback_close').click(function(){ $('#callback_cont').hide(); });
$('#callback_link').click(function(){ $('#callback_cont').toggle(); });

$(function(){
    
    if($('.usercard__comment').length > 0) {
        $('#callback_cont').prependTo($('.usercard__comment'));
    } else {
        $('#callback_cont').insertAfter($('#usercard_clear'));
    }
    
    if(!$.cookie('callback_'+callback_id)) $('#callback').show();
})

$('.btn-large-callback').click(function(){
    $('.callback_table .errorlist').hide();
    $.ajax({ 
        data: $('#callback_form').serialize(), 
        type: $('#callback_form').attr('method'), 
        url: $('#callback_form').attr('action'),
        dataType: 'json',
        beforeSend: function(jqXHR) {
            jqXHR.setRequestHeader("X-CSRFToken", $('input[name=csrfmiddlewaretoken]').val());
        },
        success: function(response) { 
            if(response.result == 'error') {
                for(var i in response.response) $('#'+i+'_error').html(response.response[i]).show();
            } else {
                $.cookie('callback_'+callback_id, '1', { expires: 1 });
                $('#callback_form_cont').hide();
                $('.callback_success').html(response.response).show();
            }
        }
    });
    return false;
});
