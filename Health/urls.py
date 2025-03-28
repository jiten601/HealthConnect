from django.urls import path
from .views import *

urlpatterns = [
    path('about/', About, name='about'),
    path('contact/', Contact, name='contact'),
    path('', Index, name='home'),
    path('login/', Login, name='login'),
    path('register/', Register, name='register'),
    path('logout/', logout_admin, name='logout'),
    path('view_doctor/', View_Doctor, name='view_doctor'),
    path('add_doctor/', Add_Doctor, name='add_doctor'),
    path('delete_doctor/<int:pid>/', Delete_Doctor, name='delete_doctor'),
    path('edit_doctor/<int:pid>/', Edit_Doctor, name='edit_doctor'),
    path('add_patient/', Add_Patient, name='add_patient'),
    path('view_patient/', View_Patient, name='view_patient'),
    path('delete_patient/<int:pid>/', Delete_Patient, name='delete_patient'),
    path('edit_patient/<int:pid>/', Edit_Patient, name='edit_patient'),
    path('add_appointment/', Add_Appointment, name='add_appointment'),
    path('view_appointment/', View_Appointment, name='view_appointment'),
    path('delete_appointment/<int:pid>/', Delete_Appointment, name='delete_appointment'),
    path('edit_appointment/<int:pid>/', Edit_Appointment, name='edit_appointment'),
] 