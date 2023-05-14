from django.shortcuts import render
from main import meme

def chat(request, code):
    return render(request, 'room.html', {'code': code, 'meme': meme})
