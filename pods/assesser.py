import pandas as pd
import numpy as np
import json
from config import config
import os

check_mark = '<span style="color:red;">**&#10004;**</span>'
check_mark = '<span style="color:red;">**Correct**</span>'

short_name = config.get('assesser', 'assessment_short_name')
long_name = config.get('assesser', 'assessment_long_name')
year = config.get('assesser', 'assessment_year')

data_directory = os.path.expandvars(config.get('assesser', 'data_directory'))

instructor_email = config.get('assesser', 'instructor_email')
instructor_name = config.get('assesser', 'instructor_name')
assesser_group_email = config.get('assesser', 'assesser_group_email')

participant_key = config.get('assesser', 'participant_list_key')
participant_sheet = config.get('assesser', 'participant_list_sheet')
marksheets_filename = config.get('assesser', 'class_marksheets_pickle')

class assessment():
    """Class for storing assesment information. This class stores the
    questions and answers for an assessment paper. It
    produces mark sheets and provides individual feedback.

    :param source: source of the exam information. If a dict then keys
    for 'spreadsheet_key' and 'worksheet_name' are expected. Questions
    will be sought in the associated google sheet. If it's a string
    that ends with 'json' then a json file will be loaded. If it's a
    string that ends with '.pickle' then a pickle file will be loaded,
    if it's a string that ends with '.csv' then a csv will be loaded.
    :type source: dict or str

    """
    
    def __init__(self, part=0, source=None, answers_sep=None, display_answer=False, display_marks=True):
        self.display_answer=display_answer
        self.display_marks=display_marks

        self.latex_preamble = r"""\documentclass[]{article}
\usepackage{a4}
\usepackage{amssymb,amsmath}
\usepackage{ifxetex,ifluatex}
\usepackage[utf8]{inputenc}
\usepackage{eurosym}
\usepackage{color}
\usepackage{fancyvrb}
\DefineShortVerb[commandchars=\\\{\}]{\|}
\DefineVerbatimEnvironment{Highlighting}{Verbatim}{commandchars=\\\{\}}
% Add ',fontsize=\small' for more characters per line
\newenvironment{Shaded}{}{}
\newcommand{\KeywordTok}[1]{\textcolor[rgb]{0.00,0.44,0.13}{\textbf{{#1}}}}
\newcommand{\DataTypeTok}[1]{\textcolor[rgb]{0.56,0.13,0.00}{{#1}}}
\newcommand{\DecValTok}[1]{\textcolor[rgb]{0.25,0.63,0.44}{{#1}}}
\newcommand{\BaseNTok}[1]{\textcolor[rgb]{0.25,0.63,0.44}{{#1}}}
\newcommand{\FloatTok}[1]{\textcolor[rgb]{0.25,0.63,0.44}{{#1}}}
\newcommand{\CharTok}[1]{\textcolor[rgb]{0.25,0.44,0.63}{{#1}}}
\newcommand{\StringTok}[1]{\textcolor[rgb]{0.25,0.44,0.63}{{#1}}}
\newcommand{\CommentTok}[1]{\textcolor[rgb]{0.38,0.63,0.69}{\textit{{#1}}}}
\newcommand{\OtherTok}[1]{\textcolor[rgb]{0.00,0.44,0.13}{{#1}}}
\newcommand{\AlertTok}[1]{\textcolor[rgb]{1.00,0.00,0.00}{\textbf{{#1}}}}
\newcommand{\FunctionTok}[1]{\textcolor[rgb]{0.02,0.16,0.49}{{#1}}}
\newcommand{\RegionMarkerTok}[1]{{#1}}
\newcommand{\ErrorTok}[1]{\textcolor[rgb]{1.00,0.00,0.00}{\textbf{{#1}}}}
\newcommand{\NormalTok}[1]{{#1}}
\ifxetex
  \usepackage[setpagesize=false, % page size defined by xetex
              unicode=false, % unicode breaks when used with xetex
              xetex,
              colorlinks=true,
              linkcolor=blue]{hyperref}
\else
  \usepackage[unicode=true,
              colorlinks=true,
              linkcolor=blue]{hyperref}
\fi
\hypersetup{breaklinks=true, pdfborder={0 0 0}}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt plus 2pt minus 1pt}
\setlength{\emergencystretch}{3em}  % prevent overfull lines
\setcounter{secnumdepth}{0}
 

\begin{document}
\title{Lab Assessment """ + str(part+1) + "}\n"
        self.latex_post = "\n" + r"""\end{document}"""


        self.html_preamble = r"""<html>
<head>
  <title>Lab Assessment {part}</title>
  <script type="text/javascript"
    src="http://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
  </script>
</head>
<body>
  <h1>Lab Assessment {part}</h1>
""".format(part=part+1)
        self.html_post = r"""  </body>
</html>"""
        # if source is None:
        #     raise ValueError("You need to provide a source for the assesment question and answers.")
        # elif type(source) is dict:
        #     # participant list is stored in a google doc
        #     if 'spreadsheet_key' in source and 'worksheet_name' in source:
        #         self.participant_sheet = gl.sheet(spreadsheet_key=source['spreadsheet_key'],
        #                                           worksheet_name=source['worksheet_name'], 
        #                                           gd_client=self.gd_client, 
        #                                           docs_client=self.docs_client)
        #         # if gl.sheet had to login, store the details.
        #         self.gd_client = self.participant_sheet.gd_client
        #         self.docs_client = self.participant_sheet.docs_client
        #         self.answers = self.participant_sheet.read()
        #         self.users.rename(columns={'Gmail Address': 'Email'}, 
        #                           inplace=True)
        #     else:
        #         raise ValueError, "If a the source is a dictionary, then it should encode a google doc for the source with fields 'spreadsheet_key' and 'worksheet_name'."

        # elif type(source) is str:
        #     # source list is stored in a file.
        #     if target.endswith(".csv"):
        #         self.source=os.path.join(self.class_dir, source)
        #         self.answers = pd.read_csv(self.source, sep=answers_sep)
        #     elif target.endswidth(".pickle"):
        #         import pickle
        #         self.source=os.path.join(self.class_dir, source)
        #         self.answers = pickle.load(open(self.source, "rb"))
        #     elif target.endswidth(".json"):
        #         import json
        #         self.source=os.path.join(self.class_dir, source)
        #         self.answers = json.load(open(self.source, "rb"))
                
        # else:
        #     raise ValueError, "Could not determine type of source file."
        self.answers = answer(part)
            
    def latex(self):
        """Gives a latex representation of the assessment."""
        output = self.latex_preamble
        output += self._repr_latex_()
        output += self.latex_post
        return output

    def html(self):
        """Gives an html representation of the assessment."""
        output = self.html_preamble
        output += self._repr_html_()
        output += self.html_post
        return output


    def _repr_html_(self):
        from IPython.nbconvert.filters.markdown import markdown2html
        return markdown2html(self._repr_md_())

    def _repr_latex_(self):
        from IPython.nbconvert.filters.markdown import markdown2latex
        return markdown2latex(self._repr_md_())

    def _repr_md_(self):
        output = ''
        
        for qu, answer in enumerate(self.answers):
            output += '#### Assignment Question ' + str(qu+1) + '\n\n'
            mark = 0
            question = ''
            for number, part in enumerate(answer):
                if number==0:
                    # First part is the intro ramble
                    if type(part) is list or type(part) is tuple:
                        output += '' + part[0] + '\n\n'
                        if len(part)>1 and part[1] is False:
                            display_subs = False
                        else:
                            display_subs = True
                    elif len(part)>0:
                        output += '' + part + '\n\n'
                        display_subs = True
                    else:
                        display_subs = True

                else:                    
                    if display_subs:
                        question += ' ' + part[0] 
                    mark += part[2]
                    if (len(part)>3 and part[3] and not self.display_answer):
                        pass
                    else:
                        output += question
                        if self.display_answer:
                            if part[1] == check_mark:
                                output += ' '
                            else:
                                output += '\n\n'
                        question = ''
                        if self.display_answer:
                            output += '\n\n**Answer**\n\n' + part[1] + '\n\n'
                        if part[2]>0 and self.display_marks:
                            output += ' *' + str(mark) + ' marks*\n\n'
                        mark=0
        return output
    
    def marksheet(self):
        """Returns an pandas empty dataframe object containing rows and columns for marking. This can then be passed to a google doc that is distributed to markers for editing with the mark for each section."""
        columns=['Number', 'Question', 'Correct (a fraction)', 'Max Mark', 'Comments']
        mark_sheet = pd.DataFrame() 
        for qu_number, question in enumerate(self.answers):
            part_no = 0
            for number, part in enumerate(question):
                if number>0:
                    if part[2] > 0:
                        part_no += 1
                        index = str(qu_number+1) +'_'+str(part_no)
                        frame = pd.DataFrame(columns=columns, index=[index])
                        frame.loc[index]['Number'] = index
                        frame.loc[index]['Question'] = part[0]
                        frame.loc[index]['Max Mark'] = part[2]
                        mark_sheet =  mark_sheet.append(frame)

        return mark_sheet.sort(columns='Number')

    def total_marks(self):
        """Compute the total mark for the assessment."""
        total = 0
        for answer in self.answers:
            for number, part in enumerate(answer):
                if number>0:
                    if part[2]>0:
                        total+=part[2]
        return total

class feedback(assessment):
    """A class for providing student feedback."""
    def __init__(self, marksheet, part=0):
        assessment.__init__(self, part, display_answer=True, display_marks=False)
        self.marksheet=marksheet
        for qu in xrange(len(self.answers)):
            mark = 0
            question = ''
            counter = 0
            for number in xrange(len(self.answers[qu])):

                if number==0:
                    if type(self.answers[qu][number]) is list or type(self.answers[qu][number]) is tuple:
                        if len(self.answers[qu][number])>1 and self.answers[qu][number][1] is False:
                            self.answers[qu][number][1] = True
                else:  
                    mark = self.answers[qu][number][2]
                    if not np.isnan(mark) and mark > 0:
                        counter += 1
                        index = str(qu+1) + '_' + str(counter)
                        fraction = marksheet.loc[index]['Correct (a fraction)']
                        if fraction<1:
                            # Markers might write unicode in their
                            # comments, need to handle this here.
                            comment = marksheet.loc[index]['Comments']
                            
                            if type(comment) is float:
                                if np.isnan(comment):
                                    comment = ''
                            else:
                                if str(comment) != 'nan':
                                    comment = '<span style="color:red;">*Marker comment*:' + ' ' + str(comment) + '</span>\n\n'
                                else:
                                    comment = ''
                            if self.answers[qu][number][1] == '':
                                self.answers[qu][number][1] = '<span style="color:red;">No **-' + str((1-fraction)*mark) + ' mark(s)**</span> ' + comment
                            else:
                                self.answers[qu][number][1] = '' + comment + '<span style="color:red;">**Correct Answer:**</span>\n\n' + self.answers[qu][number][1] + '\n\n<span style="color:red;">**-' + str((1-fraction)*mark) + ' mark(s)**</span>'
                        else:
                            self.answers[qu][number][1] = check_mark
    def _repr_md_(self):
        import numpy as np
        total = np.ceil((self.marksheet['Correct (a fraction)']*self.marksheet['Max Mark']).sum())
        if np.isnan(total):
            return '### We do not have a record of a submitted assignment.\n\n#### Total Mark: 0'
        else:
            return '### <span style="color:red;">Total Marks ' + str(total) + '</span>\n\n' + assessment._repr_md_(self) 

        
def answer(part, module='mlai2014.json'):
    """Returns the answers to the lab classes."""
    marks = json.load(open(os.path.join(data_directory, module), 'rb'))
    return marks['Lab '  + str(part+1)]
