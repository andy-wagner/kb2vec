from flask import Flask, request, Response
import logging
import requests
import codecs
from os.path import join
from time import time
import re
from ttl import remove_classref, add_nonsense_response     

endpoint = "http://localhost:8080/spotlight"
data_dir = "data/"
no_classref = True


app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("nif_ws.py")



@app.route("/proxy", methods=['POST'])
def proxy():
    h = {key: value for key, value in request.headers}
    r = requests.post(endpoint, headers=h, data=request.data)

    resp = Response()
    if r.status_code == 200:
        for header_name, header_value in r.headers.items():
            resp.headers[header_name] = header_value
        
        r_content = str(r.content, "utf-8")
        resp_data = remove_classref(r_content) if no_classref else r_content
        resp.data = resp_data

        fid = str(time()).replace(".","")
        request_fpath = join(data_dir, fid + "-request.ttl") 
        with codecs.open(request_fpath, "w", "utf-8") as req:
            req.write(str(request.data, "utf-8"))

        response_fpath = join(data_dir, fid + "-response.ttl") 
        with codecs.open(response_fpath, "w", "utf-8") as res:
            res.write(resp_data)

    else:
        log.info("Warning: server returned an error")
        log.info(r)

    return resp


@app.route("/trivial", methods=['POST'])
def trivial():
    h = {key: value for key, value in request.headers}
    
    resp_data = add_nonsense_response(request.data)

    resp = Response()
    for header_name, header_value in request.headers.items():
        resp.headers[header_name] = header_value
    resp.data = resp_data

    return resp

