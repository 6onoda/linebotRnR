from cloudant import Cloudant
from flask import Flask, render_template, request, jsonify, abort
import cf_deployment_tracker
import os
import json
import urllib.request, urllib.parse

import pysolr
from watson_developer_cloud import RetrieveAndRankV1


from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

# Emit Bluemix deployment event
cf_deployment_tracker.track()

app = Flask(__name__)

config_file = open('config.json' , 'r')
config = json.load(config_file)

line_channel_token = config["lineChannelToken"]
line_channel_secret = config["lineChannelSecret"]

rnr_user = config["RnR_USERNAME"]
rnr_pass = config["RnR_PASSWORD"]
rnr_collection = config["RnR_COLLECTION"]
rnr_cluster_id = config["RnR_CLUSTER_ID"]
rnr_ranker_id  = config["RnR_RANKER_ID"]

retrieve_and_rank = RetrieveAndRankV1(
      username = rnr_user,
      password = rnr_pass)

solrclient = retrieve_and_rank.get_pysolr_client(rnr_cluster_id , rnr_collection)

# On Bluemix, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8081
port = int(os.getenv('PORT', 8080))


line_bot_api = LineBotApi(line_channel_token)
handler = WebhookHandler(line_channel_secret)


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
 
    #query_string = event.message.text.encode("utf-8")
    query_string = urllib.parse.quote(event.message.text.encode("utf-8"), safe='')
    results = solrclient._send_request("GET", path="/fcselect?q=%s&ranker_id=%s&wt=json&fl=ranker.confidence,title,url" % (query_string, rnr_ranker_id))

    reply=""
    
    if len(json.loads(results)["response"]["docs"]) == 0:
       reply="見つかりませんでした。"

    else:
    #    for doc in json.loads(results)["response"]["docs"]:
        for i, doc in enumerate(json.loads(results)["response"]["docs"]):
            reply += doc["title"] + "\n" + doc["url"] + "\n\n"
            # max 3 docs
            if i >= 2:
                break       
            # only one for confidence == 0 if >= 3 items 
            if doc["ranker.confidence"] <= 0 :
                break
                
    line_bot_api.reply_message(
          event.reply_token,
          TextSendMessage(text=reply.rstrip() ))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
