String.prototype.capitalizeFirstLetter = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
};

var Task = Backbone.Model.extend({
    urlRoot: '/mobile_api/crm/tasks/',
    initialize: function() {
        this.on("add", this.changeName, this);
        this.on("remove", this.changeName, this);
    },
    changeName: function(model, collection, options) {
        if (model.isNew()) { // model.hasChanged() ||
            model.save();
        }
        if (taskPage.collection)
            taskPage.renderItems();
    },
    parse: function(response){
        response['start'] = moment(response['start']);
        response['end'] = moment(response['end']);
        return response;
    },
    toJSON: function () {
        var json = _.clone(this.attributes);
        json.start = this.get('start').format("YYYY-MM-DD HH:mm:00");
        json.end = this.get('end').format("YYYY-MM-DD HH:mm:00");
        json.expired = this.get('end') < moment();

        json.date = this.get('start').format("DD.MM.YYYY");
        json.start_hour = this.get('start').format("HH:00");
        json.end_hour = this.get('end').format("HH:00");

        return json;
    }
});

var TaskCollection = Backbone.Collection.extend({
    model: Task,
    url: '/mobile_api/crm/tasks/',
    parse: function(response){
        return response.results;
    },
    onlyActive: function () {
        now = moment();
        filtered = this.filter(function (task) {
            return task.get("end") > now;
        });
        return new TaskCollection(filtered);
    }
});


function getWeekDays(hours) {
    return _.map(_.range(7), function(day){
        var date = moment().weekday(day);
        return {
            id: date.format('YYMMDD'),
            label: date.format('dddd, DD').capitalizeFirstLetter(),
            date: date.format('DD.MM.YYYY'),
            hours: hours
        }
    });
}
function getMonthDays() {
    var today = moment();
    var start_day = 1 - today.date(1).day() + 1;
    return _.map(_.range(start_day, today.daysInMonth()+1), function(num){
        var date = today.clone().date(num);
        return {
            id: date.format('YYMMDD'),
            day: date.format('D'),
            date: date.format('DD.MM.YYYY'),
            title_class: num > 0 ? '' : 'prev_month'
        }
    });
}

// ячейка с задачей на календаре
var TaskView = Backbone.View.extend({
    tagName: 'span',
    className: 'task build',
    render: function() {
        var duration = this.getDuration();

        this.$el.append(this.model.get('name'));
        this.$el.attr('type', this.model.toJSON()['expired'] ? 1 : 2);
        this.$el.css({height:40*duration, lineHeight: 40*duration+'px'});

        this.$el.appendTo($(this.getCalendarId()));

        // смещение элемент относительно времени начала задачи
        var needed_offset = (parseInt(this.model.get('start').format("m"))/ 60 * 40);
        if (this.$el.closest('#week_tasks, #day_tasks').length && this.el.offsetTop != needed_offset) {
            this.$el.css({'top': needed_offset - this.el.offsetTop, position:'relative'});
        }

        return this;
    },
    getCalendarId: function() {
        var date = moment(this.model.get('start'));
        return '#c' + date.format('YYMMDDHH') + ', #c' + date.format('YYMMDD') + ' section';
    },
    getDuration: function() {
        return moment.duration(moment(this.model.get('end')).diff(moment(this.model.get('start')))).asMinutes() / 60;
    },
    events: {
        "click": function(e) {
            if (taskPage.sidebar)
                taskPage.sidebar.remove();

            taskPage.sidebar = new TaskDetail({model: this.model});

            // оставнавливает обработку клика для родительских элементов, т.к. на них появляется события для сворачивания TaskDetail
            e.stopPropagation();
        }
    }
});

var TaskPage = Backbone.View.extend({
    el: Crm.panel,
    collection: null,
    sidebar: null,
    templates: {
        'week': $('#task_week').html(),
        'month': $('#task_month').html(),
        'day': $('#task_day').html()
    },
    initialize: function() {
        this.today = moment();
        this.hours = _.map(_.range(0,24), function(num){ return String('0000000' + num % 24).slice(-2)});
        this.weekDays = getWeekDays(this.hours);
        this.monthDays = getMonthDays();
        this.collection = new TaskCollection();

        $('select#task_switch').change(function() {
            taskPage.render();
        });

        $('select#task_filter').change(function() {
            taskPage.renderItems();
        });

        // при клике вне sidebar удаляет его View
        $(document).click(function(e) {
            if (taskPage.sidebar && $(e.target).parents().length > 1 && $(e.target).closest(taskPage.sidebar.$el).length == 0) {
                taskPage.sidebar.remove();
            }
        });
    },
    render: function(options) {
        Crm.Navigation.highlight('tasks');
        Crm.Navigation.mode('tasks');

        options = options || {};
        period = $('#task_switch').val();
        data = {
            today: {id:this.today.format('YYMMDD'), label: this.today.format('dddd, D MMMM YYYY').capitalizeFirstLetter()},
            hours: this.hours,
            weekDays: this.weekDays,
            monthDays: this.monthDays
        };
        this.$el.html( Mustache.to_html(this.templates[period], data) );

        if (period != 'month') {
            var day_line_offset = (moment().get('hour') + moment().get('minute') / 60) * 40 + 60;
            setTimeout(function() {$('#time').css(Global.return_transform(0, day_line_offset, 0)).addClass('build')}, 50);
        }

        // промотка до конца диалога
        $("#week_tasks .wrapper, #day_tasks .wrapper").scrollTop(370);

        this.collection.fetch({
            success: function(collection, response, options) {
                taskPage.collection = collection;
                taskPage.renderItems();
            }
        });
    },
    renderItems: function() {
        $(Crm.panel).find('span.task').remove();
        var items = this.collection;

        if ($('select#task_filter').val() == 'active') {
            items = items.onlyActive();
        }

        items.forEach(function(item) {
            var task = new TaskView({model:item});
            task.render();
        });
    },
    events: {
        // клик на пустую ячейку
        'click .cell': function(e) {
            var $cell = $(e.currentTarget);
            var start = moment(($cell.data('date') || moment().format("DD.MM.YYYY"))+ ' ' + $cell.data('hour'), 'DD.MM.YYYY HH:mm');
            var task = new Task({start: start, end: start.clone().add(1, 'h')});

            // убираем предыдущие с других ячеек, если такие есть
            if (taskPage.sidebar)
                taskPage.sidebar.remove();

            if (!$cell.data('bs.popover')) {
                taskPage.sidebar = new TaskAdd({model: task});
                taskPage.sidebar.showPopover($cell);
            }

            // оставнавливает обработку клика для родительских элементов, т.к. на них появляется события для сворачивания TaskDetail
            e.stopPropagation();
        }
    }
});


var TaskDetail = Backbone.View.extend({
    tagName: 'section',
    id: 'task_details',
    className: 'tt_parent',

    templates: $('#task_detail').html(),
    panel: "#tasks",

    initialize: function() {
        this.render();
    },
    render: function(options) {
        this.$el.html( Mustache.to_html(this.templates, this.model.toJSON()) );
        $(this.panel).addClass('task_details').append(this.$el);

        if (this.model.attributes.lead_dict) {
            var view = this;
            var lead = new Lead(this.model.attributes.lead_dict);
            lead.on("change", function(model, name) {
                view.model.set('lead_dict', model.attributes);
            });

            var clientInfo = new ClientInfo({el: this.$el.find('.client-info'), model:lead});
            clientInfo.render();
        }

    },
    remove: function() {
        this.$el.remove();
        this.stopListening();
        $(this.panel).removeClass('task_details');
        return this;
    },
    events: {
        'click .delete_task': function() {
            this.model.destroy();
            this.remove();
        }
    }
});

var TaskAdd = Backbone.View.extend({
    templates: $('#task_add').html(),
    panel: "#tasks",

    initialize: function() {
        this.render();
    },
    render: function(options) {
        this.$el.html( $(Mustache.to_html(this.templates, this.model.toJSON())) );
        this.$el.find("input.date").datepicker({
            container: 'form.task-add', language:'ru', autoclose:true, todayHighlight:true
        });

        var $el = this.$el;
        $el.find('input.lead-autocomplete').typeahead({
            minLength: 2,
            source: function (query, process) {
                return $.get('/mobile_api/crm/leads/',
                    {query: query},
                    function (data) {
                        objects = _.map(data.results, function(obj){return {id:obj.id, name:obj.name+' '+obj.phone, obj_name:obj.name, obj_phone:obj.phone}});
                        return process(objects);
                    });
            }
        }).change(function(e) {
            var current = $(e.target).typeahead("getActive");
            if (current && current.name == $(e.target).val()) {
                $('input[name=lead]', $el).val(current.id);
                $('input[name=lead_name]', $el).val(current.obj_name);
                $('input[name=lead_phone]', $el).val(current.obj_phone);
            } else {
                $('input[name=lead]', $el).val('');
            }
        });

        return this;
    },
    remove: function() {
        var $popover = this.$el.closest('.popover');
        $("[aria-describedby='" + $popover.attr('id') + "']").popover('destroy');
        $popover.remove();
        this.stopListening();
        return this;
    },
    showPopover: function($obj) {
        $obj.popover({html: true, content:this.$el,  placement: 'auto right', container:'#crm_panel', animation:false, trigger:'manual',
            template: '<div class="popover object_tooltip" role="tooltip"><div class="arrow"></div><div class="popover-content"></div></div>'});

        $obj.on('shown.bs.popover', function(e) {
            var $popover = $(".popover");
            if ($popover.css("left") != "auto" && parseInt($popover.css("left").replace("px", "")) < 0 ) {
                $popover.css('left', '10');
            }
        });

        $obj.popover('show');
    },
    events: {
        'click .close-button': "remove",
        'submit form': function(e) {
            e.preventDefault();

            var task = this.model;
            var self = this;
            $.each(['name', 'basead', 'lead', 'lead_name', 'lead_phone', 'note'], function(i, field) {
                task.set(field, self.$('[name='+field+']').val());
            });

            task.set('start', moment(this.$('[name=date]').val() + ' ' + this.$('[name=start_hour]').val(), "DD.MM.YYYY HH:mm"));
            task.set('end', moment(this.$('[name=date]').val() + ' ' + this.$('[name=end_hour]').val(), "DD.MM.YYYY HH:mm"));

            if (taskPage.collection)
                taskPage.collection.add(task);

            this.remove();
        }
    }
});

var taskPage = new TaskPage();
