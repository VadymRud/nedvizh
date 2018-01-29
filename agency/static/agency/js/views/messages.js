var Message = Backbone.Model.extend({
    url: '/mobile_api/crm/messages/',
    getDay: function() {
        var time = moment(this.get('time'));
        return time.format('D MMMM YYYY');
    },
    toJSON: function () {
        var json = _.clone(this.attributes);

        json.isOffer = (json.subject == 'counteroffer');

        if (this.get('time')) {
            var time = moment(this.get('time'));
            var today = moment();

            if (today.isSame(time, 'day')) {
                json.time_human = time.format('HH:mm');
            } else if (today.isSame(time, 'week')) {
                json.time_human = time.format('ddd');
            } else {
                json.time_human = time.format('DD.MM');
            }
            json.time_str = time.format('DD.MM.YYYY HH:mm');
        }

        return json;
    }
});

var DialogCollection = Backbone.Collection.extend({
    model: Message,
    url: '/mobile_api/crm/messages/?dialogs',

    parse: function(response){
        return response.results;
    }
});


var DialogsPage =  Backbone.View.extend({
    el: Crm.panel,
    template: $('#dialogs-page').html(),
    collection: null,

    initialize: function() {
        $('select#dialog_lead_type').change(this.applyFilters);
        $('input#dialog_search').keyup(_.debounce(this.applyFilters, 500));
    },
    applyFilters: function() {
        if ($('#messages').length)
                dialogsPage.renderItems();
    },
    render: function() {
        // $('input#dialog_search').val(''); // закладка для очищения поиска при переходе в список сообщений
        this.renderItems();
        return this;
    },
    renderItems: function() {
        this.collection = new DialogCollection();
        var page = this;

        filter__params = {
            lead_type: $('select#dialog_lead_type').val(),
            query: $('input#dialog_search').val()
        };

        this.collection.fetch({
            data: $.param(filter__params),
            success: function(collection, response) {
                Crm.Navigation.highlight('messages');
                Crm.Navigation.mode('messages');
                page.$el.html( Mustache.to_html(page.template, {models: page.collection.toJSON()}) );
                
                // Удаляем HTML из превью сообщения
                $('#messages').find('.message p').each(function () {
                    $(this).text($('<span/>').html($(this).text()).text());
                });
            }
        });
    },
    events: {
        "click .message" : "openDialogue",
        "click .message .rm" : "deleteDialogue"
    },
    openDialogue: function(e) {
        if (!$(e.target).is('.object_id')) {
            var id = $(e.target).closest('.message').data('id');
            pageRouter.navigate('dialogue/'  + id, {trigger: true});
        }
    },
    deleteDialogue: function(e) {
        if (confirm("Вы уверены?")) {
            var id = $(e.target).closest('.message').data('id');
            this.collection.each(function (e) {
                if (e.get('root_message') == id) {
                    e.url = '/mobile_api/crm/message/' + id;
                    e.id = id;
                    e.destroy();
                }
            });
            $("#message-" + id).remove();
        }
        e.stopPropagation();
    }
});

/* Сообщения */
var MessageCollection = Backbone.Collection.extend({
    model: Message,
    url: '/mobile_api/crm/messages/',
    lead: null,
    parse: function(response){
        this.lead = response.lead;
        this.unreaded = response.unreaded;
        this.id = response.id;

        return response.results;
    }
});

var MessagesPage =  Backbone.View.extend({
    el: Crm.panel,
    templates: {
        'dialog': $('#messages-page').html(),
        'promo': $('#promo-messages-page').html()
    },
    collection: null,
    dialog_id: null,

    render: function(options) {
        this.collection = new MessageCollection();
        this.dialog_id = options.dialog_id;
        var page = this;

        this.collection.fetch({
            data: {'root_message':this.dialog_id, ordering:'-time'},
            success: function(collection, response) {
                page.collection = collection;

                if (page.collection.models[0].get('is_promo')) {
                    page.$el.html( Mustache.to_html(page.templates['promo'], {models:collection.toJSON()}));

                    var message_id = ('message_id' in options) ? options.message_id : _.first(collection.models).get('id');
                    $('#message-' + message_id).click();
                } else {
                    collection.models = collection.models.reverse();
                    page.$el.html(Mustache.to_html(page.templates['dialog'], collection.lead));

                    var lead = new Lead(collection.lead);
                    var clientInfo = new ClientInfo({el: page.$el.find('.client-info'), model: lead});
                    clientInfo.render();

                    page.renderItems();
                }

                // Корректируем в шапке количество непрочитанных сообщений
                if(collection.unreaded) {
                    $('.unread-messages').data('amount', collection.unreaded).removeClass('hidden');
                    $('.messages-badge').text(collection.unreaded).removeClass('hidden');
                } else {
                    $('.unread-messages, .messages-badge').addClass('hidden');
                }

                Crm.Navigation.highlight('messages');
                Crm.Navigation.mode('dialog');
            }
        });
        return this;
    },
    renderItems: function() {
        var element = $('#dialogue .chat_messages');
        var day = null;
        var person = null;
        var lead = this.collection.lead;
        element.empty();

        this.collection.forEach(function(item) {
            if (day != item.getDay()) {
                day_container = $("<section class='day'/>").appendTo(element);
                day_container.append('<h1><span>' + item.getDay() + '</span></h1>');
            }
            if ((person != item.get('from_user')) || (day != item.getDay())) {
                person_container = $("<article class='" + item.get('folder') + " clearfix'/>").appendTo(day_container);
                if (item.get('folder') == 'incomming') {
                    person_container.append('<h3 class="pink">' + lead.name + '</h3>');
                    if (lead.image_url) {
                        person_container.css('background-image', 'url(' + lead.image_url + ')');
                    }
                }
            }
            var message = $("<p/>").attr('data-id', item.get('id')).html(item.get('text')).appendTo(person_container);
            if (!item.get('readed'))
                message.addClass('new');
            if (item.get('subject') == "counteroffer")
                message.prepend('<b>Контроферта:</b><br/>');

            day = item.getDay();
            person = item.get('from_user');
        });

        // промотка до конца диалога
        $("#dialogue .chat .wrapper").scrollTop($('#dialogue .chat .chat_messages').height());
        $("#dialogue .chat .wrapper").scroll(function(e) {
            var scrolled = ($(e.target).scrollTop() > 0);
            $('#dialogue').toggleClass('build', scrolled);
        });

        setTimeout(function() {$('.chat_messages .incomming .new').addClass('readed');}, 500);
    },
    events: {
        "click .assign_event" : function(e) {
            var $button = $(e.currentTarget);
            var lead = this.collection.lead;
            var task = new Task({
                start: moment().add(1, 'd'), end: moment().add(1, 'd').add(1, 'h'),
                basead:lead.ad_id,  lead:lead.id, lead_name:lead.name, lead_phone:lead.phone
            });

            if (!$button.data('bs.popover')) {
                var taskAdd = new TaskAdd({model: task});
                taskAdd.showPopover($button);
            }

            // оставнавливает обработку клика для родительских элементов, т.к. на них появляется события для сворачивания TaskAdd
            e.stopPropagation();
        },
        "click .text_box .submit": function(e) {
            var $textarea = this.$el.find('textarea'),
                $button = $(e.target);
            if (!$textarea.val() || $button.is('.disabled')) return false;

            var page = this;
            $button.addClass('disabled');
            Backbone.sync(
                'create',
                new Message({root_message: this.dialog_id, text: $textarea.val()}),
                {
                    success: function () {
                        $button.removeClass('disabled');
                        $textarea.val('');
                        page.collection.fetch({
                            data: {'root_message':page.dialog_id, ordering:'time'},
                            success: function(collection, response) {
                                page.collection = collection;
                                page.renderItems();
                            }
                        });
                    }
                }
            );
        },
        "click .subject": function(e) {
            var id = $(e.currentTarget).data('id');
            var model = this.collection.get(id);
            $(e.currentTarget).addClass('active').siblings().removeClass('active');
            $('#promo .detail').html(model.get('text'));
            pageRouter.navigate("dialogue/" + this.dialog_id + "/" + id);
        }
    }
});


var dialogsPage = new DialogsPage();
var messagesPage = new MessagesPage();