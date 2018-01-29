var crm = Backbone.View.extend({
    tpl: 'crm.tpl',
    name: 'crm',
    box: '#crm',
    panel: '#crm_panel',
    init: function() {
        var self = this;
        Crm.Navigation.init();
    },
    Navigation: {
        el: '#crm .menu li',
        init: function() {
            $(document).on('click', this.el, function() {
                pageRouter.navigate($(this).data('route'), {trigger: true});
            });
        },
        highlight: function(route) {
            var $target = $(this.el).filter('[data-route="' + route + '"]');

            if (!$target.is('.active')) {
                $target.addClass('active').siblings().removeClass('active');
            }
        },
        mode: function(mode) {
            $(Crm.box).attr('mode', mode);
            $('#crm .filters').removeClass('active');
            $(this.el).filter('[data-route="' + mode + '"]').tab('show');
        }
    }
});


var Ad = Backbone.Model.extend({
    urlRoot: '/mobile_api/properties/'
});

var Tooltip = Backbone.View.extend({
    tagName: 'div',
    className: 'popover',
    template: $('#ad_tooltip').html(),

    render: function() {
        this.$el.html( Mustache.to_html(this.template, this.model.toJSON()) );
        return this;
    }
});


var ClientInfo = Backbone.View.extend({
    className: 'client-info',
    template: $('#client-info').html(),

    render: function() {
        if (this.model.get('phone') == null) {
            this.model.set('phone', '');
        }

        var model = this.model.toJSON();
        var labels = _.map(LEAD_LABELS, function(label) {
            label.selected = (label.value == model.label);
            return label;
        });
        var context = _.extend({labels: labels}, model);
        this.$el.html( Mustache.to_html(this.template, context) );
        this.setControls(); // вызывается прямо здесь, т.к. el передается во View прямо при инициализации
        return this;
    },
    submitForm: function(event) {
        var view = event.data.view;
        $('.input-like-text', view.$el).each(function(i, obj) {
            view.model.set($(obj).attr('name'), $(obj).val());
        });
        if (event.type == 'submit') {event.preventDefault();}
    },
    setControls: function() {
        var self = this;
        $('select[name=label]').selectpicker({width: 'auto'}).change(function() {
            self.model.set({
                label: self.$el.find('option:selected').val(),
                label_display: self.$el.find('option:selected').text()
            });
        });

        $('.input-like-text', this.$el).on("change", {view:this}, this.submitForm);
        $('form', this.$el).on("submit", {view:this}, this.submitForm);

        // временное решение, т.к. при использовании маски срабатывает дважды событие change
        $('.phone input').on('keydown', function(e){
            -1!==$.inArray(e.keyCode,[46,8,9,27,13,110,190])||/65|67|86|88/.test(e.keyCode)&&(!0===e.ctrlKey||!0===e.metaKey)||35<=e.keyCode&&40>=e.keyCode||(e.shiftKey||48>e.keyCode||57<e.keyCode)&&(96>e.keyCode||105<e.keyCode)&&e.preventDefault()
        });
        // phones_form.js
        //$phoneInput = $('.phone input', this.$el);
        //var value = $phoneInput.val();
        //var cleanValue = value.replace(/^(38|7)/, '');
        //$phoneInput.mask(getMask(value, cleanValue), {});
        //$phoneInput.focusin(focusIn).focusout(focusOut);
    }
});

$(document).on("mouseenter", ".object_id", function(e) {
    var $obj = $(this);
    if (!$obj.data('id') || $obj.data('bs.popover')) {
        return;
    }

    var ad = new Ad({id:$(this).data('id')});
    ad.fetch({
        success: function(model, response, options) {
            $obj.attr('href', model.attributes['website_url']).attr('target', '_blank');

            var tooltip = new Tooltip({model: model});
            var html = tooltip.render().$el.html();
            $obj.popover({html: true, animation:false, content:html,  placement: 'auto top', container:'body', trigger:'hover',
                template: '<div class="popover object_tooltip" role="tooltip"><div class="arrow"></div><div class="popover-content"></div></div>'});

            // первоначальное разворачивание popover
            if ($obj.is(':hover')) $obj.trigger('mouseenter');
        }
    });
});

var Crm = new crm();
Crm.init();

