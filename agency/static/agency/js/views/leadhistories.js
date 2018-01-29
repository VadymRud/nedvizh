var LeadHistory = Backbone.Model.extend({
    urlRoot: '/mobile_api/crm/leadhistories/',
    initialize: function() {
        this.on("change", this.onChange, this);
    },
    url: function() {
        console.log('yoo');
        var origUrl = Backbone.Model.prototype.url.call(this);
        return origUrl + (origUrl.charAt(origUrl.length - 1) == '/' ? '' : '/');
    }
});

var LeadHistoryCollection = Backbone.Collection.extend({
    model: LeadHistory,
    url: '/mobile_api/crm/leadhistories/',
    parse: function(response) {
       return response.results;
    }
});

var LeadHistoriesPage = Backbone.View.extend({
    name: 'leadhistory-list',
    el: Crm.panel,
    panel: '#leads',
    template: _.template($('#leadhistory-list').html()),
    collection: null,
    initialize: function() {
        var self = this;
        self.collection = new LeadHistoryCollection();
        $('input#leadhistories_search').keyup(_.debounce(function() {
            if ($('#leads').length) {
                self.renderItems();
            }
        }, 500));
        $('select#leadhistories_lead_type').change(function () {
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
            query: $('input#leadhistories_search').val(),
            label: $('select#leadhistories_lead_type').val()
        };
        this.collection.fetch({
            data: $.param(filterParams),
            success: function(collection, response) {
                collection.forEach(function(model) {
                    var item = new LeadHistoryItem({model: model});
                    element.append(item.el);
                    self.updateUnreadedBallonCounter(model);
                });
                Crm.Navigation.highlight('leadhistories');
                Crm.Navigation.mode('leadhistories');
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
                $('#crm').find('.menu li[data-route=leadhistories] span').addClass('hidden');
            }

            model.save();
        }
    }
});

var LeadHistoryItem = Backbone.View.extend({
    tagName: 'div',
    className: 'clearfix lead leadhistoryevent row',
    template: $('#leadhistory-item').html(),
	initialize: function() {
		this.render();
	},
    render: function() {
        $(this.el).toggleClass('new', !this.model.get('is_readed'));

        $(this.el).html( Mustache.to_html(this.template, this.model.toJSON()) );
        return this;
    },
    events: {
        "click .rm": function(e) {
            this.model.destroy();
            this.remove();
            e.stopPropagation();
        },
        "click .complain": function(e) {
            this.model.set('ask_complaint_for_call', true);
            this.model.save(null, {success: function(model, xhr, options) {
                leadHistoriesPage.renderItems();
            }});
            e.stopPropagation();
        },
        "click": function(e) {
            this.$el.removeClass('new');

            var lead_id = this.model.get('lead').id;
            var lead_history = this.model;
            leadsPage.collection.fetch({
                success: function(collection, response) {
                    var lead = collection.get(lead_id);
                    leadHistoriesPage.updateUnreadedBallon(lead_history);
                    console.log(collection, lead_id, lead);
                    leadHistoriesPage.showInfo(lead);
                }
            });
        }
    }
});

leadHistoriesPage = new LeadHistoriesPage();
