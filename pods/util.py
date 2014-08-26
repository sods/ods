import sys
import os


def display_url(target):
    """Displaying URL in an IPython notebook to allow the user to click and check on information. With thanks to Fernando Perez for putting together the implementation!"""
    from IPython.display import display, HTML
    prefix = u"http://" if not target.startswith("http") else u""
    target = prefix + target
    display(HTML(u'<a href="{t}" target=_blank>{t}</a>'.format(t=target)))

def download_url(url, store_directory, save_name = None, messages = True, suffix=''):
    """Download a file from a url and save it to disk."""
    import urllib2
    i = url.rfind('/')
    file = url[i+1:]
    print file
    dir_name = os.path.join(data_path, store_directory)
    save_name = os.path.join(dir_name, file)
    print "Downloading ", url, "->", os.path.join(store_directory, file)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    try:
        response = urllib2.urlopen(url+suffix)
    except urllib2.URLError, e:
        if not hasattr(e, "code"):
            raise
        response = e
        if response.code > 399 and response.code<500:
            raise ValueError('Tried url ' + url + suffix + ' and received client error ' + str(response.code))
        elif response.code > 499:
            raise ValueError('Tried url ' + url + suffix + ' and received server error ' + str(response.code))
    with open(save_name, 'wb') as f:
        meta = response.info()
        content_length_str = meta.getheaders("Content-Length")
        if content_length_str:
            file_size = int(content_length_str[0])
        else:
            file_size = None
        status = ""
        file_size_dl = 0
        block_sz = 8192
        line_length=30
        while True:
            buff = response.read(block_sz)
            if not buff:
                break
            file_size_dl += len(buff)
            f.write(buff)
            sys.stdout.write(" "*(len(status)) + "\r")
            if file_size:
                status = r"[{perc: <{ll}}] {dl:7.3f}/{full:.3f}MB".format(dl=file_size_dl/(1048576.),
                                                                       full=file_size/(1048576.), ll=line_length,
                                                                       perc="="*int(line_length*float(file_size_dl)/file_size))
            else:
                status = r"[{perc: <{ll}}] {dl:7.3f}MB".format(dl=file_size_dl/(1048576.),
                                                                       ll=line_length,
                                                                       perc="."*int(line_length*float(file_size_dl/(10*1048576.))))

            sys.stdout.write(status)
            sys.stdout.flush()
        sys.stdout.write(" "*(len(status)) + "\r")
        print status
        # if we wanted to get more sophisticated maybe we should check the response code here again even for successes.
