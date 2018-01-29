var Lead = Backbone.Model.extend({
    urlRoot: '/mobile_api/crm/leads/',
    initialize: function() {
        this.on("change", this.onChange, this);
    },
    onChange: function(model, options) {
        var $context = $('.client-info');
        var changedAfterSync = (options != undefined && 'xhr' in options);
        var changedAttributesKeys = Object.keys(model.changedAttributes());
        var needSave = (!changedAfterSync && $(changedAttributesKeys).filter(['label', 'name', 'phone', 'email'])).length;
        if (needSave) {
            $('input', $context).tooltip('destroy');
            model.save(null, {
                success: function(model, xhr, options) {
                    if (leadsPage.infoView) {
                        leadsPage.infoView.updateHistory();
                    }
                    if (Backbone.history.fragment == 'leads') {
                        leadsPage.renderItems();
                    }
                    if (Backbone.history.fragment == 'leadhistories') {
                        leadHistoriesPage.renderItems();
                    }
                },
                error: function(model, xhr, options) {
                    if(xhr.readyState == 4) {
                        $.each(xhr.responseJSON, function(attr, messages) {
                            $('input[name="' + attr + '"]', $context)
                                .tooltip({title:messages[0], trigger:'manual'})
                                .tooltip('show');
                        });
                    }
                }
            });
        }
        if (changedAfterSync) {
            $.each(model.changedAttributes(), function(attr, value) {
                $('input[name="' + attr + '"], select[name="' + attr + '"]', $context).val(value);
            });
        }
    }
});

var LeadCollection = Backbone.Collection.extend({
    model: Lead,
    url: '/mobile_api/crm/leads/',
    parse: function(response) {
       return response.results;
    }
});

var LeadsPage = Backbone.View.extend({
    name: 'lead-list',
    el: Crm.panel,
    panel: '#leads',
    template: _.template($('#lead-list').html()),
    collection: null,
    initialize: function() {
        var self = this;
        self.collection = new LeadCollection();
        $('input#leads_search').keyup(_.debounce(function() {
            if ($('#leads').length) {
                self.renderItems();
            }
        }, 500));
        $('select#leads_lead_type').change(function () {
            self.renderItems();
        });
        self.unreadedMessages = 0;
    },
    render: function() {
        var self = this;
        this.$el.html(this.template());
        this.$el.children().removeClass('fade');
        self.renderItems();
    },
    renderItems: function() {
        var self = this;
        var element = $('#leads .content').empty();
        var filterParams = {
            query: $('input#leads_search').val(),
            label: $('select#leads_lead_type').val()
        };
        this.collection.fetch({
            data: $.param(filterParams),
            success: function(collection, response) {
                collection.forEach(function(model) {
                    var item = new LeadItem({model: model});
                    item.$el.click(function() {
                        self.updateUnreadedBallon(model);
                        self.showInfo(model);
                    });
                    element.append(item.el);
                    self.updateUnreadedBallonCounter(model);
                });
                Crm.Navigation.highlight('leads');
                Crm.Navigation.mode('leads');
            }
        });
    },
    hideInfo: function() {
        this.infoView.remove();
        $('#leads').removeClass('info');
    },
    showInfo: function(model) {
        var self = this;
        self.infoView = new LeadInfo({model: model});
        $('.ov_content').append(self.infoView.el);
        self.infoView.updateHistory();

        $('.ov_content').click(function(e) {
            if ($(e.target).closest("#lead_info").length > 0) {
                return;
            }
            else {
                self.hideInfo();
            }
        });
        $('#leads').addClass('info');
    },
    updateUnreadedBallonCounter: function(model) {
        var self = this;
        if (!model.get('is_readed')) {
            self.unreadedMessages++;
        }
    },
    updateUnreadedBallon: function(model) {
        var self = this;
        if (!model.get('is_readed')) {
            model.set('is_readed', true);
            self.unreadedMessages--;

            if (!self.unreadedMessages) {
                $('#crm').find('.menu li[data-route=leads] span').addClass('hidden');
            }

            model.save();
        }
    }
});

var LeadItem = Backbone.View.extend({
    tagName: 'div',
    className: 'clearfix lead',
    template: $('#lead-item').html(),
	initialize: function() {
		this.render();
	},
    render: function() {
        $(this.el).html( Mustache.to_html(this.template, this.model.toJSON()) );
        return this;
    },
    events: {
        "click .rm": function(e) {
            this.model.destroy();
            this.remove();
            e.stopPropagation();
        }
    }
});

var LeadInfo = Backbone.View.extend({
    panel: ".ov_content",
    id: 'lead_info',
    tagName: 'section',
    template: $('#lead-info').html(),
	initialize: function(options) {
		this.render();
	},
    render: function() {
        this.$el.html( Mustache.to_html(this.template, this.model.toJSON()) );
        $(this.panel).append(this.$el);

        var clientInfo = new ClientInfo({el: this.$el.find('.client-info'), model:this.model});
        clientInfo.render();
    },
    updateHistory: function() {
        var $history = $('.ov_content .history>ul');
        $history.empty();
        var groupped = _.groupBy(this.model.get('history'), 'time_display');
        var pairs = _.pairs(groupped);
        var sortedPairs = _.sortBy(pairs, function(pair) {return pair[0]}).reverse();
        _.each(sortedPairs, function(pair) {
            var timeDisplay = pair[0];
            var sortedEvents = _.sortBy(pair[1], 'time');
            var messages = _.pluck(sortedEvents, 'message');
            $history.append('<li>' + timeDisplay + ' ' + messages.join(', ') + '</li>');
        });
    }
});

leadsPage = new LeadsPage();
