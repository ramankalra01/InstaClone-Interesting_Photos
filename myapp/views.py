# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from datetime import timedelta

from django.core.serializers import json
from django.http import HttpResponse
from imgurpython import ImgurClient
from instaclone.settings import BASE_DIR
from django.shortcuts import render, redirect
from django.utils import timezone

from forms import SignUpForm, LoginForm, PostForm, LikeForm, CommentForm
from models import UserModel, SessionToken, PostModel, LikeModel, CommentModel,HashTag,Hash2Post
from django.contrib.auth.hashers import make_password, check_password

### API Credentials
from clarifai.rest import ClarifaiApp
clarifai_app = ClarifaiApp(api_key="cb9a1545abae4564b05f09ed29184530")
model = clarifai_app.models.get("general-v1.3")

YOUR_CLIENT_ID = 'a8e20f3bf815329'
YOUR_CLIENT_SECRET = '3863df53283968a0e35040e1bdacb55fc3c43853'


def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = UserModel(name=name, password=make_password(password), email=email, username=username)
            user.save()
            return redirect('login/')
        else:
            form = "fillempty"
            return render(request, 'index.html', {'form': form})
    form = SignUpForm()
    return render(request, 'index.html', {'form': form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = UserModel.objects.filter(username=username).first()
            if user:
                if check_password(password, user.password):
                    token = SessionToken(user=user)
                    token.create_token()
                    token.save()
                    response = redirect('feed/')
                    response.set_cookie(key='session_token', value=token.session_token)
                    return response
                else:
                    form = 'Incorrect Password! Please try again!'
        else:
            form = 'Fill all the fields!'
    elif request.method == 'GET':
        form = LoginForm()

    return render(request, 'login.html', {'message': form})


def post_view(request):
    user = check_validation(request)
    if user:
        if request.method == 'POST':
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                image = form.cleaned_data.get('image')
                caption = form.cleaned_data.get('caption')
                post = PostModel(user=user, image=image, caption=caption)
                post.save()
                path = str(BASE_DIR +'/'+ post.image.url)
                client = ImgurClient(YOUR_CLIENT_ID, YOUR_CLIENT_SECRET)
                post.image_url = client.upload_from_path(path, anon=True)['link']
                post.save()
                concepts = model.predict_by_url(url=post.image_url)['outputs'][0]['data']['concepts']
                for concept in concepts[:5]:
                    tag = concept['name']
                    hash = HashTag.objects.filter(name  = tag)
                    if(hash.__len__() == 0):
                        hash = HashTag(name = tag)
                        hash.save()
                    else:
                        hash = hash[0]
                    Hash2Post(id_of_hashtag = hash, id_of_post = post).save()
                return redirect('/feed/')
        else:
            form = PostForm()
        return render(request, 'post.html', {'form': form})
    else:
        return redirect('/login/')

def feed_view(request):
    user = check_validation(request)
    if user:
        posts = PostModel.objects.all().order_by('-created_on')
        for post in posts:
            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()
            if existing_like:
                post.has_liked = True
        return render(request, 'feed.html', {'posts': posts})
    else:
        return redirect('/login/')

def tag_view(request):
    user = check_validation(request)
    if user:
        q = request.GET.get('q')
        hash = HashTag.objects.filter(name = q).first()
        posts = Hash2Post.objects.filter(id_of_hashtag = hash)
        posts = [post.id_of_post for post in posts]
        if (posts == []):
            return HttpResponse("<H1><CENTER>NO SUCH TAG FOUND</H1>")
        for post in posts:
            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()
            if existing_like:
                post.has_liked = True
        return render(request, 'feed.html', {'posts': posts})
    else:
        return redirect('/login/')


def like_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = LikeForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            existing_like = LikeModel.objects.filter(post_id=post_id, user=user).first()
            if not existing_like:
                LikeModel.objects.create(post_id=post_id, user=user)
            else:
                existing_like.delete()
            return redirect('/feed/')
    else:
        return redirect('/login/')


def comment_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            comment_text = form.cleaned_data.get('comment_text')
            comment = CommentModel.objects.create(user=user, post_id=post_id, comment_text=comment_text)
            comment.save()
            return redirect('/feed/')
        else:
            return redirect('/feed/')
    else:
        return redirect('/login')


# For validating the session
def check_validation(request):
    if request.COOKIES.get('session_token'):
        session = SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first()
        if session:
            time_to_live = session.created_on + timedelta(days=1)
            if time_to_live > timezone.now():
                return session.user
    else:
        return None
