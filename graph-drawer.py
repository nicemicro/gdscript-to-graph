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
        functionstart = (line[0:4] == "func" or line[0:11] == "puppet func" or
                         line[0:11] == "master func" or
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

def control_extract(operations, string, counter):
    for num, op in enumerate(operations):
        if isinstance(op, list) and op[0] != "":
            if num > 0:
                string = string  + " | "
            string = string + "{"
            string, counter = control_extract(op, string, counter)
            string = string + "}"
        elif isinstance(op, str):
            if num > 0:
                string = string  + " | "
            op = op.replace("\"", "\\\"")
            op = op.replace("'", "\\'")
            op = op.replace("{", "\\{")
            op = op.replace("}", "\\}")
            op = op.replace("<", "\\<")
            op = op.replace(">", "\\>")
            op = op.replace("\n", "\\n")
            string = string + f"<f{counter}> {op} "
            counter += 1
    return string, counter

def function_unit(function, fullname, functname):
    record = ""
    record, cnt = control_extract(function, record, 0)
    print(f"            {fullname} [")
    if record.strip():
        print(f"                label=\"<begin>{functname} | {record}\"")
    else:
        print(f"                label=\"<begin>{functname}\"")
    print("                shape=\"record\"")
    print("            ]")

def file_subgraph(file, fname, servcl, serverclient):
    fname_cut = fname.split(".")[0]
    print(f"        subgraph cluster_{servcl}_{fname_cut} " + "{")
    print(f"            label=\"{fname}\"; labeljust=\"l\";")
    for function in file:
        functype = file[function]["type"]
        if functype == serverclient or functype == place.universal:
            function_unit(file[function]["ctrl"],
                          f"{servcl}_{fname_cut}_{function}",
                          function)
    print("        }")

def sc_subgraph(files, servcl, serverclient):
    subg_name = servcl.lower().replace(" ", "")
    print(f"    subgraph cluster_{subg_name} " + "{")
    print(f"        label=\"{servcl}\"; labeljust=\"l\";")
    for filen in files:
        file_subgraph(files[filen], filen, subg_name, serverclient)
    print("    }")

def make_graph(files):
    print("digraph controlflow {")
    print("    rankdir=\"LR\";")
    sc_subgraph(files, "Client 1", place.client)
    sc_subgraph(files, "Server", place.server)
    sc_subgraph(files, "Client 2", place.client)
    print("}")

def main(cmdargs):
    show_all = False
    marker = " "
    
    opts, args = getopt.gnu_getopt(cmdargs,"m:ah",["marker=", "all"])
    for opt, arg in opts:
        if opt == "-m" or opt == "--marker":
            marker = arg
        elif opt == "-a" or opt == "--all":
            show_all = True
        elif opt == "-h":
            print("-m --marker: characters that should mark meaningful commets")
            print("-a --all:    all releavant lines should be represented")
            print("Give the directory name to crawl.")
        else:
            assert False, "unhandled commandline option"
    if len(args) == 1:
        make_graph(read_all(args[0], marker, show_all))
    
#%%
if __name__ == "__main__":
   main(sys.argv[1:])
   #a = process_file("/home/nicemicro/bin/opensus/src/game/character/character.gd", "# ", False)