# Copyright 2014 Open Data Science Initiative and other authors. See AUTHORS.txt
# Licensed under the BSD 3-clause license (see LICENSE.txt)


def display_url(target):
    """Displaying URL in an IPython notebook to allow the user to click and check on information. With thanks to Fernando Perez for putting together the implementation!"""
    from IPython.display import display, HTML
    prefix = u"http://" if not target.startswith("http") else u""
    target = prefix + target
    display(HTML(u'<a href="{t}" target=_blank>{t}</a>'.format(t=target)))

def iframe_url(target, width=500, height=400, scrolling=True, border=0, frameborder=0):
    """Produce an iframe for displaying an item in html"""
    prefix = u"http://" if not target.startswith("http") else u""
    target = prefix + target
    if scrolling:
        scroll_val = 'yes'
    else:
        scroll_val = 'no'
    return u'<iframe frameborder="{frameborder}" scrolling="{scrolling}" style="border:{border}px" src="{url}", width={width} height={height}></iframe>'.format(frameborder=frameborder, scrolling=scroll_val, border=border, url=target, width=width, height=height)

def display_iframe_url(target, **kwargs):
    """Display the contents of a URL in an IPython notebook."""
    txt = iframe_url(target, **kwargs)
    display(HTML(txt))

def display_google_book(id, page, width=700, height=500, **kwargs):
    """Display an embedded version of a Google book."""
    url = 'http://books.google.co.uk/books?id={id}&pg=PA{page}&output=embed'.format(id=id, page=page)
    display_iframe_url(url, width=width, height=height, **args)

def code_toggle(start_show=False, message=None):
    """Toggling on and off code in a notebook. 
    :param start_show: Whether to display the code or not on first load (default is False).
    :type start_show: bool
    :param message: the message used to toggle display of the code.
    :type message: string

    The tip that this idea is
    based on is from Damian Kao (http://blog.nextgenetics.net/?e=102)."""

    from IPython.display import display, HTML
    
    html ='<script>\n'
    if message is None:
        message = u'The raw code for this IPython notebook is by default hidden for easier reading. To toggle on/off the raw code, click <a href="javascript:code_toggle()">here</a>.'
    if start_show:
        html += u'code_show=true;\n'
    else:
        html += u'code_show=false;\n'
    html+='''function code_toggle() {
 if (code_show){
 $('div.input').show();
 } else {
 $('div.input').hide();
 }
 code_show = !code_show
} 
$( document ).ready(code_toggle);
</script>
'''
    html += message
    display(HTML(html))


    
