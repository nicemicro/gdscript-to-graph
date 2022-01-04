#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 23 15:11:13 2021

@author: nicemicro
"""

import os
import enum
import sys, getopt

class place(enum.Enum):
    universal = enum.auto()
    server = enum.auto()
    client = enum.auto()

def find_files(path):
    filelist = []
    for dirpath, dirs, files in os.walk(path):  
        for filename in files:
            if filename[-3:] == ".gd":
                filelist.append({"dir": dirpath, "file": filename})
    return filelist

def process_file(path, marker, show_all):
    functions = {}
    current_type = place.universal
    current_func = ""
    ftabs = 0
    tabs = 0
    prev_tabs = 0
    comment = ""
    
    # This variable keeps track of the current nesting level
    func_ctrl = []
    
    with open(path) as gdfile:
        lines = gdfile.readlines()
    for fline in lines:
        line = fline.split("#")[0]
        line = line.strip()
        if len(fline.split("#")) > 1:
            commentline = fline[fline.find("#") + 1:]
            accepted_comm = fline.find("#") != -1 and (not commentline or
                commentline[0:len(marker)] == marker or
                commentline[0:len(marker)] == marker.replace(" ", "\t"))
            if not accepted_comm:
                commentline = ""
            else:
                commentline = commentline[len(marker):]
        else:
            commentline = ""
        commentline = commentline.strip()
        tabs = len(fline) - len(fline.lstrip('\t'))

        # checks whether this line is a deliniator for server / client functs
        if (commentline[0:2] == "--" or commentline[0:3] == " --") and len(line) == 0:
            if "Server" in commentline or "server" in commentline:
                current_type = place.server
            elif "Client" in commentline or "client" in commentline:
                current_type = place.client
            continue
        
        # checks whether this line is the start of a new function
        functionstart = (line[0:4] == "func" or line[0:11] == "remote func" or
                         line[0:11] == "puppet func" or
                         line[0:11] == "master func" or
                         line[0:15] == "remotesync func" or
                         line[0:15] == "mastersync func" or
                         line[0:15] == "puppetsync func")
        if functionstart:
            funcname = line.split("func ")[1]
            funcname = funcname.split("(")[0]
            current_func = funcname
            functions[current_func] = {"type": current_type, "ctrl": []}
            func_ctrl = [functions[current_func]["ctrl"]]
            ftabs = tabs
            comment = ""
            continue
        
        # if the current tab depth is lower than the previous, we pop
        if tabs < prev_tabs and len(func_ctrl) > 0:
            for i in range(prev_tabs-tabs):
                func_ctrl.pop()
        
        if len(commentline) > 0:
            comment = comment + "\n" + commentline
        
        # ignore empty lines and ones that are not tabulated deeper than the
        # last function declaration
        if current_func != "" and line != "" and tabs > ftabs:
            controlitem = (line[-1] == ":")
            ignoreitem = (line[0:5] == "print" or line[0:6] == "assert")
            if controlitem:
                if comment == "":
                    if show_all:
                        func_ctrl[-1].append([line])
                    else:
                        func_ctrl[-1].append([""])
                else:
                    func_ctrl[-1].append([comment[1:]])
                func_ctrl.append(func_ctrl[-1][-1])
                comment = ""
            elif not ignoreitem:
                if comment == "" and show_all:
                    func_ctrl[-1].append(line)
                elif comment != "":
                    func_ctrl[-1].append(comment[1:])
                comment = ""
            else:
                comment = ""
        prev_tabs = tabs
    return functions

def read_all(path, marker, show_all):
    filelist = find_files(path)
    files = {}
    for filename in filelist:
        file = process_file(os.path.join(filename["dir"], filename["file"]),
                            marker, show_all)
        files[filename["file"]] = file
    return files

def control_extract(operations, string, counter, depth=0):
    num = 0
    for op in operations:
        if isinstance(op, list) and op[0] != "":
            if num > 0:
                string += " | "
            if num == 1 and depth > 0:
                string += " { "
            string = string + "{"
            string, counter = control_extract(op, string, counter, depth+1)
            string = string + "}"
            num += 1
        elif isinstance(op, str):
            if num > 0:
                string += " | "
            if num == 1 and depth > 0:
                string += " { "
            op = op.replace("\"", "\\\"")
            op = op.replace("'", "\\'")
            op = op.replace("{", "\\{")
            op = op.replace("}", "\\}")
            op = op.replace("<", "\\<")
            op = op.replace(">", "\\>")
            op = op.replace("\n", "\\n")
            string += f"<f{counter}> {op} "
            counter += 1
            num += 1
    if depth > 0 and num > 1:
        string += " } "
    return string, counter

def function_unit(function, fullname, functname):
    record = ""
    record, cnt = control_extract(function, record, 0)
    function_text = f"            {fullname} [\n"
    if record.strip():
        function_text += \
            f"                label=\"<begin>{functname} | {record}\"\n"
    else:
        function_text += \
            f"                label=\"<begin>{functname}\"\n"
    function_text += "                shape=\"record\"\n"
    function_text += "            ]\n"
    return function_text

def file_subgraph(file, fname, servcl, serverclient, nodes):
    fname_cut = fname.split(".")[0]
    cluster_name = f"cluster_{servcl}_{fname_cut}"
    function_units = ""
    for function in file:
        functype = file[function]["type"]
        fullname = f"{servcl}_{fname_cut}_{function}"
        show_func = ((functype == serverclient or functype == place.universal)
                     and (len(nodes)==0 or fullname in nodes))
        if show_func:
            function_units += \
                function_unit(file[function]["ctrl"], fullname, function)
    if not function_units and cluster_name not in nodes:
        return ""
    subgraph_text =  f"        subgraph {cluster_name} " + "{\n"
    subgraph_text += f"            label=\"{fname}\"; labeljust=\"l\";\n"
    subgraph_text += function_units
    subgraph_text +=  "        }\n"
    return(subgraph_text)

def sc_subgraph(files, servcl, serverclient, nodes):
    subg_name = servcl.lower().replace(" ", "")
    file_subgraphs = ""
    for filen in files:
        file_subgraphs += \
            file_subgraph(files[filen], filen, subg_name, serverclient, nodes)
    print(f"    subgraph cluster_{subg_name} " + "{")
    print(f"        label=\"{servcl}\"; labeljust=\"l\";")
    print(file_subgraphs)
    print("    }")

def make_graph(files, edges):
    print("digraph controlflow {")
    print("    rankdir=\"LR\";")
    sc_subgraph(files, "Client 1", place.client, edges["nodelist"])
    sc_subgraph(files, "Server", place.server, edges["nodelist"])
    sc_subgraph(files, "Client 2", place.client, edges["nodelist"])
    print(edges["text"])
    print("}")
    
def parse_edges(stdin, path=""):
    nodelist = []
    text = ""
    
    if stdin:
        lines = sys.stdin.readlines()
    else:
        with open(path) as gdfile:
            lines = gdfile.readlines()
    for fline in lines:
        text = text + "\n    " + fline[:-1]
        line = fline.strip()
        sep = line.find("->")
        if sep == -1:
            continue
        left = line[0:sep].strip()
        left = left.split(":")[0]
        if not left in nodelist:
            nodelist.append(left)
        right = line[sep + 2:].strip()
        right = right.split("[")[0]
        right = right.split(":")[0].strip()
        if not right in nodelist:
            nodelist.append(right)
    return {"text": text, "nodelist": nodelist}

def main(cmdargs):
    show_all = False
    marker = " "
    edges = {"text": "", "nodelist": []}
    
    opts, args = getopt.gnu_getopt(cmdargs,"m:ahsf:",
                                   ["marker=", "all", "help", "stdin", "file"])
    for opt, arg in opts:
        if opt == "-m" or opt == "--marker":
            marker = arg
        elif opt == "-a" or opt == "--all":
            show_all = True
        elif opt == "-s" or opt == "--stdin":
            newedges = parse_edges(True)
            edges["text"] = edges["text"] + newedges["text"]
            edges["nodelist"] = edges["nodelist"] + newedges["nodelist"]
        elif opt == "-f" or opt == "--file":
            newedges = parse_edges(False, arg)
            edges["text"] = edges["text"] + newedges["text"]
            edges["nodelist"] = edges["nodelist"] + newedges["nodelist"]
        elif opt == "-h" or opt == "--help":
            print("-m --marker: characters that should mark meaningful commets")
            print("-a --all:    all releavant lines should be represented")
            print("-s --stdin:  read the graph edges from standard input")
            print("-f --file:   read the graph edges from a file")
            print("Give the directory name to crawl as a cmdline argument.")
        else:
            assert False, "unhandled commandline option"
    if len(args) == 1:
        make_graph(read_all(args[0], marker, show_all), edges)
    
#%%
if __name__ == "__main__":
   main(sys.argv[1:])
   #a = process_file("/home/nicemicro/bin/opensus/src/game/character/character.gd", "# ", False)