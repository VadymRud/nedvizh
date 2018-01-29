# coding: utf-8
from django import template
import pynliner

register = template.Library()


@register.tag()
def inlinestyle(parser, token):
    nodelist = parser.parse(('endinlinestyle',))
    parser.delete_first_token()
    return InlineNode(nodelist)


class InlineNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return pynliner.fromString(output)
