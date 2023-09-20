import uuid
import boto3
import os
from django.forms.models import BaseModelForm
from django.http import HttpResponse, HttpResponseServerError, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic import ListView, DetailView
from .models import Subforum, Post, Company, Company_Subforum, Company_Post, Comment, Company_Comment, Photo, Company_Photo, Subforum_Likes, Company_Subforum_Likes
from .forms import PostForm, CommentForm, Company_PostForm, Company_CommentForm, Company_SubforumForm, SubforumForm
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.core.exceptions import PermissionDenied


# Other View Functions
# Home view function is a Subforum index
def home(request): 
    subforums = Subforum.objects.all()
    return render(request, 'home.html', { 
        'subforums': subforums
    })

def about(request): 
    return render(request, 'about.html')

# Subforum CRUD Views
# class SubforumCreate(LoginRequiredMixin, CreateView): 
#     model = Subforum
#     fields = ['title', 'pinned']

#     def form_valid(self, form): 
#         form.instance.user = self.request.user
#         return super().form_valid(form)

@login_required
def subforums_new(request): 
    subforum_form = SubforumForm()
    return render(request, 'subforum/form.html', {
        'subforum_form': subforum_form
        })

@login_required
def subforums_create(request): 
    form = SubforumForm(request.POST)
    try: 
        if form.is_valid():
            new_subforum = form.save(commit=False)
            new_subforum.user_id = request.user.id 
            new_subforum.save()
        request_files = request.FILES.getlist('photo-file', None)
        print(f'request_files: {request_files}')
        for photo_file in request_files:
            print(f'photofile: {photo_file} ')
            if photo_file:
                s3 = boto3.client('s3')
                key = uuid.uuid4().hex[:6] + photo_file.name[photo_file.name.rfind('.'):]
                try:
                    bucket = os.environ['S3_BUCKET']
                    print(f'bucket: {bucket} ')
                    s3.upload_fileobj(photo_file, bucket, key)
                    url = f"{os.environ['S3_BASE_URL']}{bucket}/{key}"
                    print(f'url: {url} ')
                    Photo.objects.create(url=url, subforum=new_subforum)
                except Exception as e:
                    print('An error occurred uploading file to S3')
                    print(e)
        return redirect('subforums_detail', subforum_id = new_subforum.id)
    except Exception as e: 
        return HttpResponseServerError(e)
        

def subforums_detail(request, subforum_id): 
    subforum = Subforum.objects.get(id=subforum_id)
    post_form = PostForm()
    comment_form = CommentForm()
    likes = len(Subforum_Likes.objects.filter(subforum=subforum_id))
    try: 
        subforum_like = Subforum_Likes.objects.get(subforum=subforum, user=request.user)
        is_liked=True
    except: 
        is_liked = False
    return render(request, 'subforum/detail.html', {
        'subforum': subforum, 
        'post_form': post_form, 
        'comment_form': comment_form, 
        'likes': likes, 
        'is_liked': is_liked
        })

class SubforumUpdate(LoginRequiredMixin, UpdateView): 
    model = Subforum
    fields = ['title', 'content']

    def user_passes_test(self,request):
        if request.user.is_authenticated: 
            self.object = self.get_object()
            return self.object.user == request.user 
        return False 
    
    def dispatch(self, request, *args, **kwargs):
        if not self.user_passes_test(request):
            raise PermissionDenied
        return super(SubforumUpdate, self).dispatch(
            request, *args, **kwargs)

@login_required
def subforums_like(request, subforum_id): 
    subforum = Subforum.objects.get(id=subforum_id)
    print(f'subforum: {subforum} ')
    try:
        subforum_like = Subforum_Likes.objects.get(subforum=subforum, user=request.user)
        print(f'subforum_like: {subforum_like} ')
        subforum_like.delete()
        is_liked=False
    except Subforum_Likes.DoesNotExist:
        Subforum_Likes.objects.create(subforum=subforum, user=request.user)
        is_liked=True
    likes = len(Subforum_Likes.objects.filter(subforum=subforum_id))
    return JsonResponse({"success": True, 'likes': likes, 'is_liked': is_liked})
    
    
@login_required
def add_post(request, subforum_id): 
    form = PostForm(request.POST)
    if form.is_valid():
        new_post = form.save(commit=False)
        new_post.subforum_id = subforum_id
        new_post.user_id = request.user.id 
        new_post.save()


    return redirect('subforums_detail', subforum_id = subforum_id)

def update_post(request, post_id, subforum_id): #double check
    post = Post.objects.get(id=post_id)
    form = PostForm(request.POST)
    if form.is_valid():
        post = form.save(commit=False)
        post.save()
    return redirect('subforum/<int:subforum_id>', subforum_id=subforum_id)

class PostDelete(LoginRequiredMixin, DeleteView): #probably add delete confirmation
    model = Post 
    def get_success_url(self): 
        subforum_id = self.object.subforum_id
        return reverse('subforums_detail', kwargs={'subforum_id': subforum_id})

    def user_passes_test(self,request):
        if request.user.is_authenticated: 
            self.object = self.get_object()
            return self.object.user == request.user 
        return False 
    
    def dispatch(self, request, *args, **kwargs):
        if not self.user_passes_test(request):
            raise PermissionDenied
        return super(PostDelete, self).dispatch(
            request, *args, **kwargs)


@login_required
def add_comment(request, subforum_id, post_id): 
    form = CommentForm(request.POST)
    if form.is_valid():
        new_comment = form.save(commit=False)
        new_comment.post_id = post_id
        new_comment.user_id = request.user.id 
        new_comment.save()
    return redirect('subforums_detail', subforum_id = subforum_id)

class CommentDelete(LoginRequiredMixin, DeleteView): #probably add delete confirmation
    model = Comment 
    def get_success_url(self): 
        subforum_id = self.object.post.subforum_id
        return reverse('subforums_detail', kwargs={'subforum_id': subforum_id})
    
    def user_passes_test(self,request):
        if request.user.is_authenticated: 
            self.object = self.get_object()
            return self.object.user == request.user 
        return False 
    
    def dispatch(self, request, *args, **kwargs):
        if not self.user_passes_test(request):
            raise PermissionDenied
        return super(CommentDelete, self).dispatch(
            request, *args, **kwargs)

class CompanyList(ListView): 
    model = Company 
    template_name = "company/index.html"

class CompanyDetail(DetailView): 
    model = Company 
    template_name = "company/detail.html"
    #query for subforums and pass the functionality of the company_subforum index 

class CompanyCreate(LoginRequiredMixin, CreateView): 
    model = Company 
    fields = '__all__'
    template_name = "company/form.html"

# Company_Subforum CRUD Views
# def company_subforum_create(request, company_id):
#     form = Company_SubforumForm(request.POST)
#     if form.is_valid(): 
#         new_company_subforum = form.save(commit=False)
#         new_company_subforum.company_id = company_id
#         new_company_subforum.save()
#     return redirect('company/detail.html', company_id = company_id)

# class Company_SubforumCreate(LoginRequiredMixin, CreateView): 
#     model = Company_Subforum
#     fields = ['title', 'pinned', 'content']

#     def form_valid(self, form): 
#         form.instance.user = self.request.user
#         form.instance.company = get_object_or_404(Company, pk=self.kwargs['company_id'])
#         return super().form_valid(form)

@login_required
def company_subforums_new(request, company_id): 
    subforum_form = Company_SubforumForm()
    company = Company.objects.get(id=company_id)
    return render(request, 'company/subforum/form.html', {
        'subforum_form': subforum_form, 
        'company': company
        })

@login_required
def company_subforums_create(request, company_id): 
    form = Company_SubforumForm(request.POST)
    try: 
        if form.is_valid():
            new_subforum = form.save(commit=False)
            new_subforum.user_id = request.user.id 
            new_subforum.company_id = company_id
            new_subforum.save()
        request_files = request.FILES.getlist('photo-file', None)
        print(f'request_files: {request_files}')
        for photo_file in request_files:
            print(f'photofile: {photo_file} ')
            if photo_file:
                s3 = boto3.client('s3')
                key = uuid.uuid4().hex[:6] + photo_file.name[photo_file.name.rfind('.'):]
                try:
                    bucket = os.environ['S3_BUCKET']
                    print(f'bucket: {bucket} ')
                    s3.upload_fileobj(photo_file, bucket, key)
                    url = f"{os.environ['S3_BASE_URL']}{bucket}/{key}"
                    print(f'url: {url} ')
                    Company_Photo.objects.create(url=url, subforum=new_subforum)
                except Exception as e:
                    print('An error occurred uploading file to S3')
                    print(e)
        return redirect('company_subforums_detail', company_id = company_id, company_subforum_id = new_subforum.id)
    except Exception as e: 
        return HttpResponseServerError(e)

  
class Company_SubforumUpdate(LoginRequiredMixin, UpdateView):
    model = Company_Subforum
    fields = ['title', 'content']

    def user_passes_test(self,request):
        if request.user.is_authenticated: 
            self.object = self.get_object()
            return self.object.user == request.user 
        return False 
    
    def dispatch(self, request, *args, **kwargs):
        if not self.user_passes_test(request):
            raise PermissionDenied
        return super(Company_SubforumUpdate, self).dispatch(
            request, *args, **kwargs)

# Ben handling these
# def company_subfoums_index(request):
#     company_subforums = Company_Subforum.objects.all()
#     # Where should this live? I picked this one because this file already exists
#     return render(request, 'company_index', {
#         'company_subforums': company_subforums
#     }) 

def company_subforums_detail(request, company_id, company_subforum_id): 
    subforum = Company_Subforum.objects.get(id=company_subforum_id)
    post_form = Company_PostForm()
    comment_form = Company_CommentForm()
    likes = len(Company_Subforum_Likes.objects.filter(subforum=company_subforum_id))
    try: 
        subforum_like = Company_Subforum_Likes.objects.get(subforum=subforum, user=request.user)
        is_liked=True
    except: 
        is_liked = False
    return render(request, 'company/subforum/detail.html', {
        'subforum': subforum, 
        'likes': likes, 
        'is_liked': is_liked,
        'post_form': post_form, 
        'comment_form': comment_form 
        })

@login_required
def company_subforums_like(request, company_id, company_subforum_id): 
    subforum = Company_Subforum.objects.get(id=company_subforum_id)
    print(f'subforum: {subforum} ')
    try:
        subforum_like = Company_Subforum_Likes.objects.get(subforum=subforum, user=request.user)
        print(f'subforum_like: {subforum_like} ')
        subforum_like.delete()
        is_liked=False
    except Company_Subforum_Likes.DoesNotExist:
        Company_Subforum_Likes.objects.create(subforum=subforum, user=request.user)
        is_liked=True
    likes = len(Company_Subforum_Likes.objects.filter(subforum=company_subforum_id))
    return JsonResponse({"success": True, 'likes': likes, 'is_liked': is_liked})


# Company_Post CRUD Views
def add_company_post(request, company_id, company_subforum_id): 
    form = Company_PostForm(request.POST)
    if form.is_valid():
        new_company_post = form.save(commit=False)
        new_company_post.subforum_id = company_subforum_id
        new_company_post.user_id = request.user.id 
        new_company_post.save()
    return redirect('company_subforums_detail', company_id=company_id, company_subforum_id=company_subforum_id)

def update_company_post(request, company_post_id, company_subforum_id):
    company_post = Company_Post.objects.get(id=company_post_id)
    form = PostForm(request.POST)
    if form.is_valid():
        company_post = form.save(commit=False)
        company_post.save()
    return redirect('company_subforum/detail.html', company_subforum_id=company_subforum_id)

def add_company_comment(request, company_id, company_subforum_id, company_post_id):
    form = Company_CommentForm(request.POST)
    if form.is_valid():
        new_company_comment = form.save(commit=False)
        new_company_comment.post_id = company_post_id
        new_company_comment.user_id = request.user.id 
        new_company_comment.save()
    return redirect('company_subforums_detail', company_id=company_id, company_subforum_id = company_subforum_id)

class Company_CommentDelete(LoginRequiredMixin, DeleteView): #probably add delete confirmation
    model = Company_Comment 

    def get_success_url(self): 
        subforum_id = self.object.post.subforum_id
        company_id = self.object.post.subforum.company_id
        return reverse('company_subforums_detail', kwargs={'company_id': company_id, 'company_subforum_id': subforum_id})

    def user_passes_test(self,request):
        if request.user.is_authenticated: 
            self.object = self.get_object()
            return self.object.user == request.user 
        return False 
    
    def dispatch(self, request, *args, **kwargs):
        if not self.user_passes_test(request):
            raise PermissionDenied
        return super(Company_CommentDelete, self).dispatch(
            request, *args, **kwargs)


class Company_PostDelete(LoginRequiredMixin, DeleteView): #delete confirmation 
    model = Company_Post

    def get_success_url(self): 
        subforum_id = self.object.subforum_id
        company_id = self.object.subforum.company_id 
        return reverse('company_subforums_detail', kwargs={'company_id': company_id, 'company_subforum_id': subforum_id})

    def user_passes_test(self,request):
        if request.user.is_authenticated: 
            self.object = self.get_object()
            return self.object.user == request.user 
        return False 
    
    def dispatch(self, request, *args, **kwargs):
        if not self.user_passes_test(request):
            raise PermissionDenied
        return super(Company_PostDelete, self).dispatch(
            request, *args, **kwargs)



def signup(request): 
    error_message = ''
    if request.method == 'POST': 
        form = UserCreationForm(request.POST)
        if form.is_valid(): 
            user = form.save()
            login(request, user)
            return redirect('index')
        else: 
            error_message = "Invalid sign up - try again"
    form = UserCreationForm()
    context = {'form': form, 'error_message': error_message}
    return render(request, 'registration/signup.html', context)

