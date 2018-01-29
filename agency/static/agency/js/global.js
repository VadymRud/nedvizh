moment.locale('ru');

var _sync = Backbone.sync;
Backbone.sync = function(method, model, options){
    // Add trailing slash to backbone model views
    var parts = _.result(model, 'url').split('?'),
        _url = parts[0],
        params = parts[1];

    _url += _url.charAt(_url.length - 1) == '/' ? '' : '/';

    if (!_.isUndefined(params)) {
        _url += '?' + params;
    };

    options = _.extend(options, {
        url: _url
    });

    return _sync(method, model, options);
};

var Global = {
    main_box: '#content_box',
    tpl_path: crm_tpl_path,
    
    Fancy: {
        wait: null,
        transition_process: false,
        transition: function(callback) {
            console.log(this.transition_process);
            if (this.transition_process) return;
            var main = $(Crm.panel);
            var c = main.children();
            this.transition_process = true;
            if (c.length !== 0) {
                c.addClass('fade');
                setTimeout(function() {
                    c.remove();
                    callback();
                    wait_for_content();
                }, 500);
            } else {
                console.log('no content');
                callback();
                wait_for_content();
            }

            function wait_for_content() {
                Global.Fancy.wait = setInterval(function() {
                    if ($(Crm.panel).children().length !== 0) {
                        console.log('done');
                        clearInterval(Global.Fancy.wait);
                        Global.Fancy.transition_process = false;
                        setTimeout(function() {
                            $(Crm.panel).children().removeClass('fade');
                        }, 10);
                    }
                }, 1);
            }
        },
        
        build: function(block) {
            setTimeout(function() {block.addClass('build');}, 20);
        }
    },
    
    return_transform: function(x, y, z) {
        return {
            "-webkit-transform": "translate3d(" + x + "px, " + y + "px, " + z + "px)",
            "-moz-transform": "translate3d(" + x + "px, " + y + "px, " + z + "px)",
            "-ms-transform": "translate3d(" + x + "px, " + y + "px, " + z + "px)",
            "transform": "translate3d(" + x + "px, " + y + "px, " + z + "px)"
        };
    },

    render: function(tpl, name, callback, method) {
        method = method || 'html';
        callback = callback || function(){console.log('rendering ' + name + ' from ' + tpl)};
        $.Mustache.load(PageRouter.tpl_path + tpl, function() {
            $(pageRouter.main).mustache(name, {}, {method: method});
            callback();
        });
    }
};
