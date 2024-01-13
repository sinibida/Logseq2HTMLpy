import argparse # https://docs.python.org/3/library/argparse.html#action
import re # https://docs.python.org/3/library/re.html
import os
import os.path as path
import shutil

guid_regex = r'[0-9A-Fa-f]{8}[-]?[0-9A-Fa-f]{4}[-]?[0-9A-Fa-f]{4}[-]?[0-9A-Fa-f]{4}[-]?[0-9A-Fa-f]{12}'
property_regex = r"([a-zA-Z\._-]+):: (.*)"
watermark_html = "<h6>created with <code>Logseq2HTML.py</code></h6>"

def get_properties(text):
    ret = dict()
    for match in re.finditer(property_regex, text):
        ret[match.group(1)] = match.group(2)
    return ret

def get_blocks(text):
    lines = text.splitlines()

    indent_matches = [re.match(r'^(\t*)- .*', line) for line in lines]
    block_start_idx = [i for i, m in enumerate(indent_matches) if m != None]
    block_end_idx = block_start_idx[1:] + [len(lines)]
    block_indent = [len(indent_matches[i].groups()[0]) for i in block_start_idx]
    blocks = [
        {
            "num": i,
            # first
            "start_idx": p1,
            "end_idx": p2,
            "indent": p3,
            # content-wise
            "content": None,
            "parameter_content": None,
            "all_content": None,
            # TODO: add parameter dict
            "id": None,
            # relations
            "parent": None,
            "children": [],
            "next": None,
            "prev": None,
        } for i, (p1, p2, p3)
        in enumerate(zip(block_start_idx, block_end_idx, block_indent))
    ]

    for block in blocks:
        block_lines = lines[block['start_idx']:block['end_idx']]
        
        # TODO: add parameter dict
        content_lines = [x for x in block_lines if re.search(property_regex, x) == None]
        parameter_lines = [x for x in block_lines if re.search(property_regex, x) != None]

        block["parameter_content"] = '\n'.join([x.strip() for x in parameter_lines])
        block["content"] = '\n'.join([x.strip() for x in content_lines])
        block["all_content"] = '\n'.join([x.strip() for x in block_lines])
        # https://stackoverflow.com/questions/11040707/c-sharp-regex-for-guid
        block_id_match = re.search(
            f'id:: ({guid_regex})',
            block['all_content'],
        )
        if block_id_match != None:
            block["id"] = block_id_match.groups()[0]

    block_stack = []
    for block in blocks:
        while len(block_stack) > block['indent']:
            popped_block = block_stack.pop()
            if popped_block['indent'] == block['indent']:
                popped_block['next'] = block

        if len(block_stack) > 0:
            block['parent'] = block_stack[-1]
        
        block_stack.append(block)
    del block_stack

    for block in blocks:
        if block['parent'] != None:
            block['parent']['children'].append(block)
        if block['next'] != None:
            block['next']['prev'] = block

    header = '\n'.join(lines[:blocks[0]['start_idx']])

    return blocks, header

def find_block_with_id(blocks, id):
    for x in blocks:
        if x['id'] == id:
            return x
    return None

def format_block_content(s: str):
    if s.startswith('- '):
        s = s[2:]
    s = s.replace('\\mu', 'η')
    s = s.replace('\\rarr', '→')
    s = s.replace('->', '→')
    s = s.replace('\\larr', '←')
    s = s.replace('<-', '←')
    s = s.replace('\n', '<br/>');
    s = re.sub(
        r"(?:^> .+(?:\n|$))+",
        lambda m: f"<blockquote>{re.sub('> ', '', m.group(0))}</blockquote>",
        s
    )
    s = re.sub(
        r"~{2}([^~]+)~{2}",
        r"<s>\1</s>",
        s
    )
    s = re.sub(
        r"\*{2}([^\*]+)\*{2}",
        r"<b>\1</b>",
        s
    )
    s = re.sub(
        r"\*([^\*]+)\*",
        r"<i>\1</i>",
        s
    )
    return s

def get_block_title(block):
    child_shortened = block['content'].partition('\n')[0]
    if len(child_shortened) > 100:
        child_shortened = f"{child_shortened[:100]}..."
    return format_block_content(child_shortened)

def anchor_to_block(block, title=None):
    if block == None:
        return "<b><i>???</i></b>"
    child_link_title = get_block_title(block)
    return f"<a href=\"{block['num']}.html\">{child_link_title if title == None else title}</a>"

def replace_internal_link(block_html_content):
    block_html_content = re.sub(
        f'\\[([^\]]+)\\]\\(\\(\\(({guid_regex})\\)\\)\\)',
        lambda m: anchor_to_block(find_block_with_id(blocks, m.group(2)), title=m.group(1)),
        block_html_content,
    )
    block_html_content = re.sub(
        f'\\(\\(({guid_regex})\\)\\)',
        lambda m: anchor_to_block(find_block_with_id(blocks, m.group(1))),
        block_html_content,
    )
    return block_html_content

def blocks_to_html(blocks):
    s = ""
    s += "<ul>"
    for block in blocks:
        s += "<li>"
        if len(block['children']) > 0 and block['id'] != None:
            s += anchor_to_block(block)
        else:
            s += anchor_to_block(block, title='(#)')
            s += '&nbsp;'
            s += replace_internal_link(format_block_content(block['content']))
            if len(block['children']) > 0:
                s += blocks_to_html(block['children'])
        s += "</li>"
    s += "</ul>"
    return s

def properties_to_html(props):
    text = '\n'.join(f"{key}: {value}" for key, value in props.items())
    return f"<h6 style=\"margin: 0px\">{format_block_content(text)}</h6>"

def write_html(dir, block, template):
    # https://www.geeksforgeeks.org/create-a-directory-in-python/
    path_title = f"{block['num']}"
    path_full = dir
    # os.mkdir(path_full)

    html_text: str = template

    html_content = ""

    block_html_content:str = block['content']
    block_html_content = format_block_content(block_html_content);
    block_html_content = replace_internal_link(block_html_content)
    
    html_content += block_html_content
    html_content += properties_to_html(get_properties(block['parameter_content']))
    html_content += blocks_to_html(block['children'])
    html_content += watermark_html
    
    html_text = html_text.replace(
        "<!--BACK-->", 
        anchor_to_block(block['parent'], title=f"< BACK ({get_block_title(block['parent'])})")
        if block['parent'] != None else
        "<a href=\"index.html\">< INDEX</a>"
    )
    html_text = html_text.replace("<!--TITLE-->", get_block_title(block))
    html_text = html_text.replace("<!--CONTENT-->", html_content)

    with open(path.join(path_full, f"{path_title}.html"), "x", encoding="utf-8") as file:
        file.write(html_text)

    for child in block['children']:
        write_html(path_full, child, template)

def write_index_html(dir, blocks, page_props, template, home_url, index_title):
    html_content = ""

    roots = [block for block in blocks if block['indent'] == 0]

    html_content = ""

    html_content += properties_to_html(page_props)
    html_content += blocks_to_html(roots)
    html_content += watermark_html

    html_text = template
    
    if home_url != None:
        html_text = html_text.replace(
            "<!--BACK-->", 
            f"<a href=\"{home_url}\">< HOME</a>"
        )
    title = index_title if index_title != None else page_props['name'] if 'name' in page_props.keys() else "index"
    html_text = html_text.replace("<!--TITLE-->", title)
    html_text = html_text.replace("<!--CONTENT-->", html_content)

    with open(path.join(dir, "index.html"), "x", encoding="utf-8") as file:
        file.write(html_text)

    for x in roots:
        write_html(dir, x, html_template)

parser = argparse.ArgumentParser(
                    prog='Logseq2HTML',
                    description='Converts logseq note into buncha htmls',
                    epilog='Text at the bottom of help')

parser.add_argument('filename')
parser.add_argument('-o', '--output', default="output", required=False, help="Output directory.")
parser.add_argument('-t', '--template', default="template.html", required=False, help="HTML Template.")
parser.add_argument('-H', '--home', default=None, required=False, help="The URL where the '< HOME' link of index.html links to.")
parser.add_argument('-T', '--title', default=None, required=False, help="Title of index.html (defaults to `name` property of note)")

args = parser.parse_args()

with open(args.filename, "r", encoding="utf-8") as file:
    text = file.read()
with open(args.template, "r", encoding="utf-8") as file:
    html_template = file.read()

blocks, header = get_blocks(text)
page_props = get_properties(header)
print(page_props)

if path.exists(args.output):
    shutil.rmtree(args.output)
os.mkdir(args.output)
write_index_html(args.output, blocks, page_props, html_template, args.home, args.title)
    