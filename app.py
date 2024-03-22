from flask import Flask, render_template_string, render_template, request, Response, send_from_directory
import requests
from datetime import datetime
import pytz
from markupsafe import Markup
import re
import json
import os
import time
from fractions import Fraction
import math
app = Flask(__name__)
VERY_HOT_THRESHOLD = 80.0
myid = '7050522555013682'

DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
def get_cpu_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as file:
            temp_str = file.readline().strip()
            return float(temp_str) / 1000.0
    except FileNotFoundError:
        return None

def sort_data(data, sort_by, ascending=True):
    if sort_by == 'time_until_over':
        key_func = lambda x: datetime.fromisoformat(x['end_date']) - datetime.now(pytz.UTC)
    else:
        key_func = lambda x: x[sort_by]
    return sorted(data, key=key_func, reverse=not ascending)

def calculate_time_until_over(end_date):
    current_time = datetime.now(pytz.UTC)
    end_time = datetime.fromisoformat(end_date)
    delta = end_time - current_time
    days, seconds = delta.days, delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{days}d {hours}h {minutes}m {seconds}s"

def clean_player_id(player_id):
    return player_id.split('|')[-1] if '|' in player_id else player_id
@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory(DIRECTORY, filename)

@app.route('/PauseMenuOpen.ogg')
def pause_menu_open():
    url = "https://cdn.discordapp.com/attachments/1208522139909754970/1209174647036448878/PauseMenuOpen.ogg?ex=65e5f6a5&is=65d381a5&hm=95acd52a470caffa58e5d44c7d32a13cd03f404277513e268afbf5ef44786b16"
    resp = requests.get(url)
    return Response(resp.content, mimetype='audio/ogg')

@app.route('/info') 
def info():
    response = requests.get("https://go.gunraidersapi.com/api/v27/info/all")
    data = response.json()

    banner = data['data']['banner_locker']
    banner = re.sub(r"<color=(.*?)>", r"<span style='color: \1;'>", banner)
    banner = banner.replace("</size>", "</span>").replace("</color>", "</span>")
    
    banner = Markup(banner)
    return render_template('info.html',news_items=data['data']['news'], banner=banner, ver=data['data']['version'])

@app.route('/bans') 
def ban_list():
    response = requests.get('https://go.gunraidersapi.com/api/v27/ban/all')
    data = response.json()['data']
    # THe following is the /bans page
    valid_data = []
    for item in data:
        item['time_until_over'] = calculate_time_until_over(item['end_date'])
        if datetime.fromisoformat(item['end_date']) > datetime.now(pytz.UTC):
            valid_data.append(item)

    sort_by = request.args.get('sort_by', 'time_until_over')
    order = request.args.get('order', 'asc')
    sorted_data = sort_data(valid_data, sort_by, ascending=order == 'asc')

    return render_template('bans.html', data=sorted_data)

@app.route('/items', methods=['GET', 'POST'])
def items():
    search_query = request.args.get('search', '')
    order_by = request.args.get('order_by', 'none')
    order_type = request.args.get('order_type', 'asc')

    response = requests.get("https://go.gunraidersapi.com/api/v27/store/catalog")
    data = response.json()

    if search_query:
        data['data'] = [item for item in data['data'] if search_query.lower() in item.get('item_name', '').lower()]

    if order_by == 'price':
        data['data'].sort(key=lambda x: x.get('item_price', 0), reverse=order_type == 'desc')
    elif order_by == 'rarity':
        data['data'].sort(key=lambda x: x.get('rarity', ''), reverse=order_type == 'desc')
    return render_template('items.html',items=data['data'])

@app.route('/clear')
def clear_terminal():
    os.system('clear')
    return "Terminal cleared"

@app.route('/rebootpi')
def reboot_terminal():
    os.system('sudo reboot')
    return "Rebooting..."

@app.route('/') 
def home():
    temp = get_cpu_temperature()
    if temp is not None:
        if temp >= VERY_HOT_THRESHOLD:
            print(f"CPU Temperature: {temp}°C - Very Hot!")
        else:
            print(f"CPU Temperature: {temp}°C")
    return render_template('home.html')

@app.route('/news/<int:count>') 
def news(count=20):
    if count > 200:
        count = 200

    url = f"https://go.gunraidersapi.com/api/v27/news/latest/{count}"
    response = requests.get(url)
    data = response.json()

    news_data = data.get('data', [])
    return render_template('news.html', news_items=news_data, count=count)

@app.route('/servers')
def servers():
    url = "https://go.gunraidersapi.com/api/v27/game/wholelist/plain/0.8.227_2.43/*/*"
    response = requests.get(url)
    data = response.json().get('data', [])
    for item in data:
        players = item['CustomProperties'].get('playersInRoom', [])
        item['playersString'] = ", ".join(players)
    return render_template('servers.html', server_items=data)


@app.route('/leaderboard/<string:type>/<string:period>/<int:page>')
def leaderboard(type='score', period='weekly', page=0):
    url = f"https://go.gunraidersapi.com/api/v27/leaderboard/get/16/{type}/{period}/{page}"
    response = requests.get(url)
    data = response.json()

    if data.get('status') == 200 and data.get('success'):
        leaderboard_data = data.get('data', [])
    else:
        leaderboard_data = []
    
    return render_template('leaderboard.html', leaderboard=leaderboard_data, period=period, type=type, nextpage = str(int(page) + 1), prevpage = str(int(page) - 1), page=page, firstnumber = int(page) * 16)

@app.route("/claimcoins/<string:auth>", methods=["POST"])
def claim(auth = ''):
    url = "https://go.gunraidersapi.com/api/v27/inventory/claim-daily"
    headers = {'Host': 'go.gunraidersapi.com', 'User-Agent': 'UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)', 'Accept': '*/*', 'Accept-Encoding': 'deflate, gzip', 'Authorization': '', 'Content-Type': 'multipart/form-data; boundary=DTMm7czbf6CnmvQiHDd1yrrFQb1AmvxAmKEuxfbe', 'X-Unity-Version': '2020.3.40f1', 'Content-Length': '515'}
    data = "\r\n--DTMm7czbf6CnmvQiHDd1yrrFQb1AmvxAmKEuxfbe\r\nContent-Disposition: form-data; name=\"platform\"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\nOCULUS\r\n--DTMm7czbf6CnmvQiHDd1yrrFQb1AmvxAmKEuxfbe\r\nContent-Disposition: form-data; name=\"platform_txn_id\"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n<purchase_id>\r\n--DTMm7czbf6CnmvQiHDd1yrrFQb1AmvxAmKEuxfbe\r\nContent-Disposition: form-data; name=\"platform_txn_time\"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n<purchase_time>\r\n--DTMm7czbf6CnmvQiHDd1yrrFQb1AmvxAmKEuxfbe--\r\n"
    headers["Authorization"] = auth
    response = requests.post(url, headers=headers, data=data)
    # The following is the /claimcoins page
    userresponse = """
    <html>
        <head>
            <meta http-equiv="refresh" content="5;url=/player" />
        </head>
        <body>
            <h1>Success: {response_text}</h1>
            <p>You will be redirected back to the original page in 5 seconds...</p>
        </body>
    </html>
    """.format(response_text=response.json()["success"])
    
    return userresponse

@app.route("/player", methods=["GET", "POST"])
def playerdata():
    if request.method == "POST":
        platform_id = request.form["playerid"]

        url = "https://graph.oculus.com/"+ platform_id +"?access_token=OC%7C3982869578392875%7C7583392a523a805972b32f426ca9a51c&fields=id,alias,org_scoped_id"
        headers = {
            "Host": "graph.oculus.com",
            "User-Agent": "UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "X-Unity-Version": "2020.3.40f1",
        }

        response = requests.get(
            url,
            headers=headers,
        )
        try:
            alias = response.json().get("alias")
            print(platform_id)
            print(alias)
            with open('log.txt', 'a') as file:
                file.write(alias + '\n')
        except :
            return "Error"
        playername = response.json().get("alias")
        playerid = response.json().get("org_scoped_id")
        platform_id = response.json().get("id")
        response = requests.get("https://go.gunraidersapi.com/api/v27/info/all")
        ver = response.json()['data']['version']

        url = "https://go.gunraidersapi.com/api/v27/player/register"
        headers = {
            "Host": "go.gunraidersapi.com",
            "User-Agent": "UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Content-Type": "multipart/form-data; boundary=7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF",
            "X-Unity-Version": "2020.3.40f1",
            "Content-Length": "1590",
        }
        data = (
            '\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="player_id"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n'
            + playerid
            + '\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="platform_id"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n'
            + platform_id
            + '\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="region"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n-\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="name"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n'
            + playername
            + '\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="device"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\nOculus_Quest_2\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="platform_token"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n12345\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="player_type"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\na3745f5d21f2cc8bbc136d028a5d422c\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="session"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\nE60FFF585BB24DAC72728620C84FCC5EC8859B79\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="version"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\n'
            + ver
            + '\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF\r\nContent-Disposition: form-data; name="platform"\r\nContent-Type: text/plain; encoding=utf-8\r\n\r\nOCULUS\r\n--7e28AwlCWIt2VfjoWbqt4Uide9aab90SRdQ7bOjF--\r\n'
        )
        aresponse = requests.post(url, headers=headers, data=data)
        url = "https://go.gunraidersapi.com/api/v27/bounty/get"
        headers = {
            "Host": "go.gunraidersapi.com",
            "User-Agent": "UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Authorization": "",
            "X-Unity-Version": "2020.3.40f1",
        }
        data = ""
        response_json = aresponse.json()
        try:
            access_token = response_json["data"]["access_token"]
        except KeyError:
            return "Error, ID incorrect (or banned player)"

        headers["Authorization"] = access_token
        print(access_token)
        response = requests.get(url, headers=headers)
        bounties = response.json().get("data", [])

        url = "https://go.gunraidersapi.com/api/v27/xp/get"
        headers = {
            "Host": "go.gunraidersapi.com",
            "User-Agent": "UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Authorization": "",
            "X-Unity-Version": "2020.3.40f1",
        }
        data = ""

        try:
            access_token = response_json["data"]["access_token"]
        except KeyError:
            return "Error, ID incorrect"
        headers["Authorization"] = access_token
        response = requests.get(url, headers=headers)
        xp = response.json().get("data", [])

        url = "https://go.gunraidersapi.com/api/v27/inventory/check-can-claim-daily"
        headers = {
            "Host": "go.gunraidersapi.com",
            "User-Agent": "UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Authorization": "",
            "X-Unity-Version": "2020.3.40f1",
        }
        data = ""
        try:
            access_token = response_json["data"]["access_token"]
        except KeyError:
            return "Error, ID incorrect"
        headers["Authorization"] = access_token
        response = requests.get(url, headers=headers)
        canclaim = response.json().get("data", [])

        url = "https://go.gunraidersapi.com/api/v27/player/all/0"
        headers = {
            "Host": "go.gunraidersapi.com",
            "User-Agent": "UnityPlayer/2020.3.40f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)",
            "Accept": "*/*",
            "Accept-Encoding": "deflate, gzip",
            "Authorization": "",
            "X-Unity-Version": "2020.3.40f1",
        }
        data = ""

        try:
            access_token = response_json["data"]["access_token"]
        except KeyError:
            return "Error, ID incorrect"
        headers["Authorization"] = access_token
        response = requests.get(url, headers=headers)
        alldata = response.json().get("data", [])
        allstats = alldata["stats"]
        
        wallet = alldata["wallet_balance"]
        if allstats["lifetime_deaths"] == 0:
            return "Cannot use this page for a player with 0 lifetime deaths"
        # Render the HTML page with data
        return render_template("playerdata.html", access_token=access_token, playername=playername, bounties=bounties, xp=xp, wallet=wallet, canclaim=canclaim, allstats=allstats, kdr = str(Fraction(allstats["lifetime_kills"], allstats["lifetime_deaths"]).limit_denominator()), kdrp = round((allstats["lifetime_kills"] / allstats["lifetime_deaths"]), 2) * 100, kpg = round(allstats["lifetime_kills"] / allstats["lifetime_games"]))
    
    # Render the HTML page for initial form
    return render_template("playerform.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)