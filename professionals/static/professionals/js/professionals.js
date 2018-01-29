function initCityChooser() {
    // region-choose - самодельное событие, срабатывающее при выборе города в самодельном popup-виджете выбора города
    $('#professionals_search_form').on('region-choose', function(e, id, name, static_url) {
        $('#professionals_search_form .city input').val(id);
        $('#professionals_search_form .city .button-text').text(name);
        $('#cities-choose-dropdown').modal('hide');
    });

    $('#cities-choose-dropdown').on('show.bs.modal', function (e) {
        if ($(this).data('sender').closest('#professionals_search_form').length) {$(this).addClass('hide-all-province-link');}
    }).on('hide.bs.modal', function (e) {
        if ($(this).data('sender').closest('#professionals_search_form').length) {$(this).removeClass('hide-all-province-link');}
    });
}

function initTypeFilter() {
    $('#professionals-types a').click(function(event) {
        event.preventDefault();
        $('#professionals_search_form').attr('action', $(this).attr('href')).submit();
    });
}

function showReviewForm() {
    $('#add-review-button,.result-count').hide();
    $('#review-form').show();
}

function showReplyForm(reviewId) {
    var reviewElement = $('.review[data-id=' + reviewId + ']');

    $('.add-reply-button').show();

    var addReplyContainer = reviewElement.find('.add-reply');
    addReplyContainer.find('.add-reply-button').hide();

    var form = $('#reply-form');
    form.children('input[name=review]').val(reviewId);
    form.appendTo(addReplyContainer).show();
}

function initReplyButtons() {
    $('.add-reply-button:not([data-target])').click(function (e) {
        var $replyForm = $('#reply-form');
        $replyForm.find('.js_validation_messages').remove();
        $replyForm.find('.form-group').removeClass('has-error');
        $replyForm.find('.controls > *').val('');

        var reviewId = $(this).parents('.review').data('id');
        showReplyForm(reviewId);
    });
}

function initAddReviewButton() {
    $('#add-review-button:not([data-target],[disabled])').click(function (e) {
        showReviewForm()
    });
}

function updateReviewFormRating() {
    var ratingValue = $('#review-form input[name=rating]').val();
    $.each($('#review-form .rating li'), function(index, element) {
        if (index + 1 <= ratingValue) {
            $(this).addClass('active');
        } else {
            $(this).removeClass('active');
        }
    });
}

function initReviewForm() {
    $('#review-form .rating li').click(function(e) {
        var ratingValue = $(this).data('value');
        $('#review-form input[name=rating]').val(ratingValue);
        updateReviewFormRating();
    });
}

function initSendMessageButton() {
    $('a.send-message').click(function(e) {
        e.preventDefault();
        $("#message-modal .modal-body").html('<iframe width="100%" height="290" frameborder="0" scrolling="auto" src="' + this.href + '"></iframe>');
        $('#message-modal').modal({show:true})
    });
}

$(function() {
    initCityChooser();
    initTypeFilter();
    initReplyButtons();
    initAddReviewButton();
    initReviewForm();
    initSendMessageButton();
});

