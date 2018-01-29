var PageRouter = Backbone.Router.extend({

    currentView: null,

    routes: {
        '': function() {
            dialogsPage.render();
        },
        'messages': function() {
            dialogsPage.render();
        },
        'leads': function() {
            leadsPage.render();
        },
        'leadhistories': function() {
            leadHistoriesPage.render();
        },
        'dialogue/:id': function(id) {
            messagesPage.render({dialog_id:id});
        },
        'dialogue/:id/:msg_id': function(id, msg_id) {
            messagesPage.render({dialog_id:id, message_id: msg_id});
        },
        'tasks': function() {
            taskPage.render();
        }
    }

});

var pageRouter = new PageRouter();

$(function () {
    Backbone.history.start();
});


