# Copyright 2014 Open Data Science Initiative and other authors. See AUTHORS.txt
# Licensed under the BSD 3-clause license (see LICENSE.txt)

import os
import IPython

if int(IPython.__version__[0]) > 3:
    from ipywidgets import interact, fixed
else:
    from IPython.html.widgets.interaction import interact, fixed
from IPython.display import display, HTML, IFrame, Image, SVG


def display_url(target):
    """Displaying URL in an IPython notebook to allow the user to click and check on information. With thanks to Fernando Perez for putting together the implementation!
    :param target: the url to display.
    :type target: string."""

    prefix = u"http://" if not target.startswith("http") else u""
    target = prefix + target
    display(HTML(u'<a href="{t}" target=_blank>{t}</a>'.format(t=target)))


def iframe_url(target, width=500, height=400, scrolling=True, border=0, frameborder=0):
    """Produce an iframe for displaying an item in HTML window.
    :param target: the target url.
    :type target: string
    :param width: the width of the iframe (default 500).
    :type width: int
    :param height: the height of the iframe (default 400).
    :type height: int
    :param scrolling: whether or not to allow scrolling (default True).
    :type scrolling: bool
    :param border: width of the border.
    :type border: int
    :param frameborder: width of the frameborder.
    :type frameborder: int"""

    prefix = u"http://" if not target.startswith("http") else u""
    target = prefix + target
    if scrolling:
        scroll_val = "yes"
    else:
        scroll_val = "no"
    return u'<iframe frameborder="{frameborder}" scrolling="{scrolling}" style="border:{border}px" src="{url}", width={width} height={height}></iframe>'.format(
        frameborder=frameborder,
        scrolling=scroll_val,
        border=border,
        url=target,
        width=width,
        height=height,
    )


def display_iframe_url(target, **kwargs):
    """Display the contents of a URL in an IPython notebook.
    
    :param target: the target url.
    :type target: string

    .. seealso:: `iframe_url()` for additional arguments."""

    txt = iframe_url(target, **kwargs)
    display(HTML(txt))


def display_google_book(id, page=None, width=600, height=450, **kwargs):
    """Display an embedded version of a Google book.
    :param id: the id of the google book to display.
    :type id: string
    :param page: the start page for the book.
    :type id: string or int."""
    if isinstance(page, int):
        url = "https://books.google.co.uk/books?id={id}&pg=PA{page}&output=embed".format(
            id=id, page=page
        )
    else:
        url = "https://books.google.co.uk/books?id={id}&pg={page}&output=embed".format(
            id=id, page=page
        )
    IFrame(url, width=width, height=height, **kwargs)


def code_toggle(start_show=False, message=None):
    """Toggling on and off code in a notebook. 
    :param start_show: Whether to display the code or not on first load (default is False).
    :type start_show: bool
    :param message: the message used to toggle display of the code.
    :type message: string

    The tip that this idea is
    based on is from Damian Kao (http://blog.nextgenetics.net/?e=102)."""

    html = "<script>\n"
    if message is None:
        message = (
            u"The raw code for this jupyter notebook can be hidden for easier reading."
        )
    if start_show:
        html += u"code_show=true;\n"
    else:
        html += u"code_show=false;\n"
    html += """function code_toggle() {
 if (code_show){
 $('div.input').show();
 } else {
 $('div.input').hide();
 }
 code_show = !code_show
} 
$( document ).ready(code_toggle);
</script>
"""
    html += (
        message
        + ' To toggle on/off the raw code, click <a href="javascript:code_toggle()">here</a>.'
    )
    display(HTML(html))


def display_prediction(
    basis,
    num_basis=4,
    wlim=(-1.0, 1.0),
    fig=None,
    ax=None,
    xlim=None,
    ylim=None,
    num_points=1000,
    offset=0.0,
    **kwargs
):
    """Interactive widget for displaying a prediction function based on summing separate basis functions.
    :param basis: a function handle that calls the basis functions.
    :type basis: function handle.
    :param xlim: limits of the x axis to use.
    :param ylim: limits of the y axis to use.
    :param wlim: limits for the basis function weights."""

    import numpy as np
    import pylab as plt

    if fig is not None:
        if ax is None:
            ax = fig.gca()

    if xlim is None:
        if ax is not None:
            xlim = ax.get_xlim()
        else:
            xlim = (-2.0, 2.0)
    if ylim is None:
        if ax is not None:
            ylim = ax.get_ylim()
        else:
            ylim = (-1.0, 1.0)

    # initialise X and set up W arguments.
    x = np.zeros((num_points, 1))
    x[:, 0] = np.linspace(xlim[0], xlim[1], num_points)
    param_args = {}
    for i in range(num_basis):
        lim = list(wlim)
        if i == 0:
            lim[0] += offset
            lim[1] += offset
        param_args["w_" + str(i)] = tuple(lim)

    # helper function for making basis prediction.
    def predict_basis(w, basis, x, num_basis, **kwargs):
        Phi = basis(x, num_basis, **kwargs)
        f = np.dot(Phi, w)
        return f, Phi

    if type(basis) is dict:
        use_basis = basis[list(basis.keys())[0]]
    else:
        use_basis = basis
    f, Phi = predict_basis(np.zeros((num_basis, 1)), use_basis, x, num_basis, **kwargs)
    if fig is None:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.set_ylim(ylim)
        ax.set_xlim(xlim)

    predline = ax.plot(x, f, linewidth=2)[0]
    basislines = []
    for i in range(num_basis):
        basislines.append(ax.plot(x, Phi[:, i], "r")[0])

    ax.set_ylim(ylim)
    ax.set_xlim(xlim)

    def generate_function(
        basis,
        num_basis,
        predline,
        basislines,
        basis_args,
        display_basis,
        offset,
        **kwargs
    ):
        w = np.zeros((num_basis, 1))
        for i in range(num_basis):
            w[i] = kwargs["w_" + str(i)]
        f, Phi = predict_basis(w, basis, x, num_basis, **basis_args)
        predline.set_xdata(x[:, 0])
        predline.set_ydata(f)
        for i in range(num_basis):
            basislines[i].set_xdata(x[:, 0])
            basislines[i].set_ydata(Phi[:, i])

        if display_basis:
            for i in range(num_basis):
                basislines[i].set_alpha(1)  # make visible
        else:
            for i in range(num_basis):
                basislines[i].set_alpha(0)
        display(fig)

    if type(basis) is not dict:
        basis = fixed(basis)

    plt.close(fig)
    interact(
        generate_function,
        basis=basis,
        num_basis=fixed(num_basis),
        predline=fixed(predline),
        basislines=fixed(basislines),
        basis_args=fixed(kwargs),
        offset=fixed(offset),
        display_basis=False,
        **param_args
    )


def display_plots(filebase, directory=None, width=600, height=450, **kwargs):
    """Display a series of plots controlled by sliders. The function relies on Python string format functionality to index through a series of plots."""

    def show_figure(filebase, directory, width=600, height=450, **kwargs):
        """Helper function to load in the relevant plot for display."""
        _, ext = os.path.splitext(filebase)
        filename = filebase.format(**kwargs)
        if directory is not None:
            filename = directory + "/" + filename
        if ext.lower() == ".svg":
            display(SVG(data="{filename}".format(filename=filename)))
        elif ext.lower() in [".png", ".jpg", ".gif", ".jpeg"]:
            display(
                Image(
                    data="{filename}".format(filename=filename),
                    width=width,
                    height=height,
                )
            )
        elif ext.lower() in [".html"]:
            display(
                IFrame(
                    src="{filename}".format(filename=filename),
                    width=width,
                    height=height,
                )
            )

    interact(
        show_figure,
        filebase=fixed(filebase),
        directory=fixed(directory),
        width=fixed(width),
        height=fixed(height),
        **kwargs
    )
