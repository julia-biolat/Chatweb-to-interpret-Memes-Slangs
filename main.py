from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from elasticsearch import Elasticsearch
from django.shortcuts import render


# Flask 애플리케이션과 SocketIO 서버 초기화
app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds" # Flask 애플리케이션의 비밀 키 설정
socketio = SocketIO(app)

# 방 및 단어에 대한 설명을 저장하는 딕셔너리 초기화
rooms = {}
meme = {}

# Elasticsearch 서버에 단어를 검색하는 함수
def es(word):
    # Elasticsearch 인스턴스에 연결
    es = Elasticsearch(
        cloud_id="LingoLink:dXMtY2VudHJhbDEuZ2NwLmNsb3VkLmVzLmlvOjQ0MyRmNWZhZTdmZDQzMDY0ODljOGE2NDJmZjE1NGM0NWE5MCQ0Zjg0NTYwN2QxMjg0ZjVjOTU5Yzc2ZTRmNGQ4Y2NmMA==",
        basic_auth=("elastic", "******")
    )

    # 인덱스에 쿼리를 실행
    response = es.search(
    index = "data00-ana",
    query = {
        "multi_match": {
    "query": word,
    "fields": ["column1"]
    }
    }
    )
    
    # Elasticsearch의 응답을 반환
    return response["hits"]["hits"] if response["hits"]["total"]["value"] > 0 else None


# 고유한 방 코드 생성 함수
def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break

    return code

# 메시지 내의 단어를 볼드체로 표시하고, 해당 단어에 마우스를 올리면 설명이 표시되도록 하는 함수
def boldify_message(message, es_response):
    if es_response is None:
        return message
    for hit in es_response:
        word = hit["_source"]["column1"]
        explanation = hit["_source"]["column2"]  # 단어에 대한 설명이 저장된 필드가 'column2'라고 가정
        if word in message:
            message = message.replace(word, f'<a href="#" onclick="alert(\'{explanation}\')"><b>{word}</b></a>')
    return message


# 홈 페이지 라우트. 사용자는 여기서 채팅방을 생성하거나 기존 채팅방에 참여할 수 있습니다.
@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        # 필요한 정보를 입력하도록 요청
        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)

        # 채팅방 생성
        room = code
        if create != False:
            room = generate_unique_code(4) # 새로운 방 코드 생성
            rooms[room] = {"members": 0, "messages": []} # 방 정보 초기화
        elif code not in rooms: # 방이 존재하지 않는 경우 오류 메시지 표시
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        # 세션에 사용자 이름과 방 정보 저장
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

# 채팅방 페이지 라우트. 사용자는 이 페이지에서 채팅을 할 수 있습니다.
@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    return render_template("room.html", code=room, messages=rooms[room]["messages"], meme=meme)

# 채팅 메시지를 처리하는 함수
@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    content = {
        "name": session.get("name"),
        "message": data["data"]
    }
    meme = es(content["message"]) # 메시지에서 단어 검색
    bold_message = boldify_message(content["message"], meme)  # meme 단어에 대해 볼드체 처리
    content["message"] = bold_message
    send(content, to=room) # 메시지를 방에 전송
    rooms[room]["messages"].append(content) # 메시지를 방의 메시지 목록에 추가
    print(f"{session.get('name')} said: {data['data']}")

# 사용자가 채팅방에 접속했을 때 처리하는 함수
@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room) # 사용자를 방에 추가
    send({"name": name, "message": "has entered the room"}, to=room) # 방에 입장 메시지 전송
    rooms[room]["members"] += 1 # 방의 멤버 수 증가
    print(f"{name} joined room {room}")

# 사용자가 채팅방에서 나갔을 때 처리하는 함수
@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room) # 사용자를 방에서 제거

    if room in rooms:
        rooms[room]["members"] -= 1 # 방의 멤버 수 감소
        if rooms[room]["members"] <= 0: # 멤버가 더 이상 없는 경우
            del rooms[room] # 방을 제거

    send({"name": name, "message": "has left the room"}, to=room) # 방에 퇴장 메시지 전송
    print(f"{name} has left the room {room}") # 콘솔에 퇴장 메시지 출력

# 메인 엔트리 포인트. Flask 애플리케이션과 SocketIO 서버를 시작합니다.
if __name__ == "__main__":
    socketio.run(app, debug=True) # 디버그 모드로 Flask 애플리케이션과 SocketIO 서버 실행
