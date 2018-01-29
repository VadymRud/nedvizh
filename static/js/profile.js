function prepareMainCheckbox() {
    $('#choose-all-ad').change(function() {
        $('.checkbox-in-list').prop('checked', $(this).is(':checked'));
        showActionMenu();
    }).prop('checked', false);
}

function prepareListCheckboxes() {
    $('#my-properties-form').on('change', '.property-short .checkbox-in-list', function() {
        showActionMenu();
    }).find('.checkbox-in-list').prop('checked', false);
}

function showActionMenu() {
    var $selected_ads = $('.property-short .checkbox-in-list:checked').closest('.property-short');
    var inactive_selected_ads = $selected_ads.filter('.inactive').length;
    var active_ads_for_sold = $selected_ads.filter('.need_reason_for_deactivation').length;

    $('#choose-all-ad').prop('checked', $selected_ads.length);
    $('.show-when-ads-selected').toggleClass('hidden', $selected_ads.length == 0);
    $('.hide-when-ads-selected').toggleClass('hidden', $selected_ads.length > 0);

    $('#my-properties-form .group-actions .action-activate').toggleClass('hidden', inactive_selected_ads == 0);
    $('#my-properties-form .group-actions .action-deactivate').toggleClass('hidden', $selected_ads.length == inactive_selected_ads);
    $('#my-properties-form .group-actions .action-sold').toggleClass('hidden', active_ads_for_sold == 0);
}

function preparePaginationStep() {
    var $hiddenInput = $('#id_per_page');

    $('.value-to-form').unbind('click').click(function() {
        $hiddenInput.val($(this).data('value'));
        $hiddenInput.parent().submit();

        return false;
    });
}

$().ready(function() {
    if($('#my-properties-form').length) {
        prepareListCheckboxes();
        prepareMainCheckbox();
        preparePaginationStep();

        updateStatusFilter();
        updateDealTypeFilter();
        updatePropertyTypeFilter();
    }

    if($('form.profile-form').length) {
        initPhonesFormset();
    }
});

function initPhonesFormset() {
    $($('form.profile-form .field_phone').slice(1).get().reverse()).each(function(index, element) {
        var $element = $(element);
        if (!$element.find('input').val()) {
            $element.hide();
        } else {
            return false;
        }
    });

    $('form.profile-form .add-extra-phone a').click(function(e) {
        $('form.profile-form .field_phone:hidden').first().show();
        if ($('form.profile-form .field_phone:hidden').length == 0) {
            $('form.profile-form .add-extra-phone').hide();
        }
        e.preventDefault();
    });
}

function selectStatusFilter(status_) {
    $('#my-properties-filter-form input[name=status]').val(status_);
    updateStatusFilter();
    $('#my-properties-filter-form').submit();
}

function updateStatusFilter() {
    status_ = $('#my-properties-filter-form input[name=status]').val();
    statusText = $('#my-properties-filter-form a.status-' + status_).text();
    $('#my-properties-filter-form span.selected-status').text(statusText.replace(/ \d+/, ''));
}

function selectDealTypeFilter(dealType) {
    $('#my-properties-filter-form input[name=deal_type]').val(dealType);
    updateDealTypeFilter();
    $('#my-properties-filter-form').submit();
}

function updateDealTypeFilter() {
    status_ = $('#my-properties-filter-form input[name=deal_type]').val();
    statusText = $('#my-properties-filter-form a.deal-type-' + status_).text();
    $('#my-properties-filter-form span.selected-deal-type').text(statusText);
}

function selectPropertyTypeFilter(dealType) {
    $('#my-properties-filter-form input[name=property_type]').val(dealType);
    updatePropertyTypeFilter();
    $('#my-properties-filter-form').submit();
}

function updatePropertyTypeFilter() {
    status_ = $('#my-properties-filter-form input[name=property_type]').val();
    statusText = $('#my-properties-filter-form a.property-type-' + status_).text();
    $('#my-properties-filter-form span.selected-property-type').text(statusText);
}

function onFilterFormSubmit() {
    $('#my-properties-filter-form input').filter(function() {return !this.value}).prop('disabled', true);
}
