$(function() {
    $.each(
        $('input.calendars'), function() {
            InstallLionBarsWidget(this.name);
            InstallCalendarWidget(this.name);
            HideAdminBookingField(this.name);
        }
    );
});

function HideAdminBookingField(name) {
    $(".field-" + name + "_booking").hide();
}

function SetReservedClass($calendars, obj, className) {
    $.each(obj, function(index, value) {
        $calendars.find('td[name=' + value + ']').addClass(className);
    });
}

function InstallCalendarWidget(name) {
    var $calendars = $('.calendars .calendar'),
        $daily_input = $('input#id_' + name);
        $daily_input_booking = $('input#id_' + name + '_booking');
        
    if ($daily_input.val())
        SetReservedClass($calendars, $.evalJSON( $daily_input.val() ), 'busy');

    if ($daily_input_booking.val())
        SetReservedClass($calendars, $.evalJSON( $daily_input_booking.val() ), 'booking');
    
    $calendars.find('td.booking').attr('title', 'Забронировано через Колл-центр mesto.ua');

    $('td', $calendars).not('.noday').not('.booking').css('cursor', 'pointer').click(function() {
        $(this).toggleClass('busy');
        UpdateInput();
    });
    
    function UpdateInput() {    
        var res = [];
        $calendars.each(function() {
            $(this).find('td.busy').each(function() {
                res.push($(this).attr('name'));
            });
        });
        $daily_input.val($.toJSON(res));
    }
}

function InstallLionBarsWidget(name) {
    var $bars = $('.lionbars, .calendars');
    var collapsed = $('fieldset.collapsed');
    var container = $('.field-' + name + ':hidden');
    
    collapsed.removeClass('collapsed');
    container.show();
    
    $bars.lionbars();
    collapsed.addClass('collapsed');

    if (!collapsed.length) container.hide();
}

