# Health/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout, login
from django.db import connection
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from .models import Doctor, Patient, Appointment, ContactMessage

@require_http_methods(["GET"])
def About(request):
    return render(request, 'about.html')

@require_http_methods(["GET"])
def Contact(request):
    return render(request, 'contact.html')

@require_http_methods(["GET"])
def Index(request):
    if not request.user.is_staff:
        return redirect('login')
    doctors = Doctor.objects.all().order_by('id')
    patients = Patient.objects.all().order_by('id')
    appointments = Appointment.objects.all().order_by('id')

    d = len(doctors)
    p = len(patients)
    a = len(appointments)
    
    context = {'d': d, 'p': p, 'a': a}
    return render(request, 'index.html', context)

@require_http_methods(["GET", "POST"])
def Login(request):
    error = ""
    if request.method == 'POST':
        u = request.POST['uname']
        p = request.POST['pwd']
        user = authenticate(username=u, password=p)
        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect('home')
            else:
                error = "You don't have admin privileges"
        else:
            error = "Invalid username or password"
    return render(request, 'login.html', {'error': error})

@csrf_protect
@require_http_methods(["GET", "POST"])
def Register(request):
    error = ""
    if request.method == 'POST':
        fullname = request.POST['fullname']
        email = request.POST['email']
        username = request.POST['username']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']
        
        if password != confirm_password:
            error = "Passwords do not match"
        else:
            try:
                # Check if username already exists
                if User.objects.filter(username=username).exists():
                    error = "Username already exists"
                # Check if email already exists
                elif User.objects.filter(email=email).exists():
                    error = "Email already exists"
                else:
                    # Validate password strength
                    try:
                        validate_password(password)
                        # Create user with staff privileges
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password,
                            first_name=fullname.split()[0],
                            last_name=' '.join(fullname.split()[1:]) if len(fullname.split()) > 1 else '',
                            is_staff=True  # Grant staff privileges
                        )
                        # Automatically log in the user with the ModelBackend
                        user.backend = 'django.contrib.auth.backends.ModelBackend'
                        login(request, user)
                        return redirect('home')  # Redirect to dashboard
                    except ValidationError as e:
                        error = '; '.join(e.messages)
            except Exception as e:
                error = str(e)
    
    return render(request, 'register.html', {'error': error})

def logout_admin(request):
    if not request.user.is_staff:
        return redirect('login')
    logout(request)
    return redirect('login')

def View_Doctor(request):
    if not request.user.is_staff:
        return redirect('login')
    doc = Doctor.objects.all().order_by('id')  # Order by ID for consistency
    d = {'doc': doc}
    return render(request, 'view_doctor.html', d)
   
def Add_Doctor(request):
    error = ""
    if not request.user.is_staff:
        return redirect('login')
    if request.method == 'POST':
        n = request.POST['name']
        m = request.POST['mobile']
        s = request.POST['special']
        try:
            doc = Doctor.objects.create(name=n, mobile=m, special=s)
            doc.save()
            error = "no"
            return redirect('view_doctor')  # Redirect to view_doctor page after successful addition
        except:
            error = "yes"
    d = {'error': error}
    return render(request, 'add_doctor.html', d)

def Delete_Doctor(request, pid):
    if not request.user.is_staff:
        return redirect('login')
    
    # Step 1: Delete the doctor (this will also delete related appointments due to CASCADE)
    doctor = get_object_or_404(Doctor, id=pid)
    doctor.delete()

    # Step 2: Renumber the remaining doctors and update related appointments
    with connection.cursor() as cursor:
        # SQLite doesn't support SET FOREIGN_KEY_CHECKS, so we skip it
        # (SQLite handles foreign keys differently and enforces them per transaction)

        # Get all remaining doctors ordered by current ID
        remaining_doctors = Doctor.objects.all().order_by('id')

        # Create a mapping of old IDs to new IDs
        old_to_new_ids = {}
        new_id = 1
        for d in remaining_doctors:
            old_to_new_ids[d.id] = new_id
            new_id += 1

        # Get all appointments before deleting doctors
        appointments = Appointment.objects.all()
        appointment_data = [
            {
                'doctor_id': appt.doctor_id,  # Store the old doctor ID
                'patient': appt.patient,
                'date1': appt.date1,
                'time1': appt.time1
            }
            for appt in appointments
        ]

        # Delete all doctors and appointments
        Doctor.objects.all().delete()
        Appointment.objects.all().delete()

        # Reset the auto-increment counter for Doctor
        if connection.vendor == 'sqlite':
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='Health_doctor';")
        elif connection.vendor == 'mysql':
            cursor.execute('ALTER TABLE Health_doctor AUTO_INCREMENT = 1;')
        elif connection.vendor == 'postgresql':
            cursor.execute("SELECT setval(pg_get_serial_sequence('Health_doctor', 'id'), 1, false);")

        # Re-insert doctors with new IDs
        new_doctors = {}
        for d in remaining_doctors:
            new_doctor = Doctor.objects.create(
                name=d.name,
                mobile=d.mobile,
                special=d.special
            )
            new_doctors[old_to_new_ids[d.id]] = new_doctor

        # Re-insert appointments with updated doctor IDs
        for appt in appointment_data:
            old_doctor_id = appt['doctor_id']
            if old_doctor_id in old_to_new_ids:  # Only re-insert if the doctor still exists
                new_doctor_id = old_to_new_ids[old_doctor_id]
                Appointment.objects.create(
                    doctor=new_doctors[new_doctor_id],
                    patient=appt['patient'],
                    date1=appt['date1'],
                    time1=appt['time1']
                )

        # No need to re-enable foreign key checks for SQLite

    return redirect('view_doctor')

def Add_Patient(request):
    error = ""
    if not request.user.is_staff:
        return redirect('login')
    if request.method == 'POST':
        n = request.POST['name']
        m = request.POST.get('mobile', None)  # Handle optional field
        g = request.POST['gender']
        a = request.POST['address']
        try:
            # Convert mobile to int if provided, else None
            mobile = int(m) if m else None
            patient = Patient.objects.create(name=n, mobile=mobile, gender=g, address=a)
            patient.save()
            error = "no"
            return redirect('view_patient')  # Redirect to view_patient page after successful addition
        except ValueError:
            error = "yes"  # Invalid mobile number format
        except Exception:
            error = "yes"  # Other errors
    d = {'error': error}
    return render(request, 'add_patient.html', d)

def View_Patient(request):
    if not request.user.is_staff:
        return redirect('login')
    patients = Patient.objects.all().order_by('id')  # Order by ID for consistency
    d = {'patients': patients}
    return render(request, 'view_patient.html', d)

def Delete_Patient(request, pid):
    if not request.user.is_staff:
        return redirect('login')
    
    # Step 1: Delete the patient (this will also delete related appointments due to CASCADE)
    patient = get_object_or_404(Patient, id=pid)
    patient.delete()

    # Step 2: Renumber the remaining patients and update related appointments
    with connection.cursor() as cursor:
        # SQLite doesn't support SET FOREIGN_KEY_CHECKS, so we skip it
        # (SQLite handles foreign keys differently and enforces them per transaction)

        # Get all remaining patients ordered by current ID
        remaining_patients = Patient.objects.all().order_by('id')

        # Create a mapping of old IDs to new IDs
        old_to_new_ids = {}
        new_id = 1
        for p in remaining_patients:
            old_to_new_ids[p.id] = new_id
            new_id += 1

        # Get all appointments before deleting patients
        appointments = Appointment.objects.all()
        appointment_data = [
            {
                'doctor': appt.doctor,
                'patient_id': appt.patient_id,  # Store the old patient ID
                'date1': appt.date1,
                'time1': appt.time1
            }
            for appt in appointments
        ]

        # Delete all patients and appointments
        Patient.objects.all().delete()
        Appointment.objects.all().delete()

        # Reset the auto-increment counter for Patient
        if connection.vendor == 'sqlite':
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='Health_patient';")
        elif connection.vendor == 'mysql':
            cursor.execute('ALTER TABLE Health_patient AUTO_INCREMENT = 1;')
        elif connection.vendor == 'postgresql':
            cursor.execute("SELECT setval(pg_get_serial_sequence('Health_patient', 'id'), 1, false);")

        # Re-insert patients with new IDs
        new_patients = {}
        for p in remaining_patients:
            new_patient = Patient.objects.create(
                name=p.name,
                mobile=p.mobile,
                gender=p.gender,
                address=p.address
            )
            new_patients[old_to_new_ids[p.id]] = new_patient

        # Re-insert appointments with updated patient IDs
        for appt in appointment_data:
            old_patient_id = appt['patient_id']
            if old_patient_id in old_to_new_ids:  # Only re-insert if the patient still exists
                new_patient_id = old_to_new_ids[old_patient_id]
                Appointment.objects.create(
                    doctor=appt['doctor'],
                    patient=new_patients[new_patient_id],
                    date1=appt['date1'],
                    time1=appt['time1']
                )

        # No need to re-enable foreign key checks for SQLite

    return redirect('view_patient')

def Add_Appointment(request):
    error = ""
    if not request.user.is_staff:
        return redirect('login')
    
    # Fetch all doctors and patients to populate the dropdowns
    doctors = Doctor.objects.all().order_by('id')
    patients = Patient.objects.all().order_by('id')

    if request.method == 'POST':
        doctor_id = request.POST['doctor']
        patient_id = request.POST['patient']
        date1 = request.POST['date1']
        time1 = request.POST['time1']
        
        try:
            # Get the selected doctor and patient objects
            doctor = Doctor.objects.get(id=doctor_id)
            patient = Patient.objects.get(id=patient_id)
            
            # Create the appointment
            appointment = Appointment.objects.create(
                doctor=doctor,
                patient=patient,
                date1=date1,
                time1=time1
            )
            appointment.save()
            error = "no"
            return redirect('view_appointment')  # Redirect to view_appointment page after successful addition
        except Exception as e:
            error = "yes"
            print(f"Error creating appointment: {e}")  # For debugging

    d = {
        'doctors': doctors,
        'patients': patients,
        'error': error
    }
    return render(request, 'add_appointment.html', d)

# Already in Health/views.py
def View_Appointment(request):
    if not request.user.is_staff:
        return redirect('login')
    appointments = Appointment.objects.all().order_by('id')  # Order by ID for consistency
    d = {'appointments': appointments}
    return render(request, 'view_appointment.html', d)

def Delete_Appointment(request, pid):
    if not request.user.is_staff:
        return redirect('login')
    
    # Step 1: Delete the appointment
    appointment = get_object_or_404(Appointment, id=pid)
    appointment.delete()

    # Step 2: Renumber the remaining appointments
    with connection.cursor() as cursor:
        # SQLite doesn't support SET FOREIGN_KEY_CHECKS, so we skip it
        # (SQLite handles foreign keys differently and enforces them per transaction)

        # Get all remaining appointments ordered by current ID
        remaining_appointments = Appointment.objects.all().order_by('id')

        # Create a mapping of old IDs to new IDs
        old_to_new_ids = {}
        new_id = 1
        for appt in remaining_appointments:
            old_to_new_ids[appt.id] = new_id
            new_id += 1

        # Store the appointment data (including foreign keys)
        appointment_data = [
            {
                'doctor': appt.doctor,
                'patient': appt.patient,
                'date1': appt.date1,
                'time1': appt.time1
            }
            for appt in remaining_appointments
        ]

        # Delete all appointments
        Appointment.objects.all().delete()

        # Reset the auto-increment counter for Appointment
        if connection.vendor == 'sqlite':
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='Health_appointment';")
        elif connection.vendor == 'mysql':
            cursor.execute('ALTER TABLE Health_appointment AUTO_INCREMENT = 1;')
        elif connection.vendor == 'postgresql':
            cursor.execute("SELECT setval(pg_get_serial_sequence('Health_appointment', 'id'), 1, false);")

        # Re-insert appointments with new IDs
        for appt in appointment_data:
            Appointment.objects.create(
                doctor=appt['doctor'],
                patient=appt['patient'],
                date1=appt['date1'],
                time1=appt['time1']
            )

        # No need to re-enable foreign key checks for SQLite

    return redirect('view_appointment')

def Edit_Doctor(request, pid):
    if not request.user.is_staff:
        return redirect('login')
    
    doctor = get_object_or_404(Doctor, id=pid)
    error = ""
    
    if request.method == 'POST':
        n = request.POST['name']
        m = request.POST['mobile']
        s = request.POST['special']
        try:
            doctor.name = n
            doctor.mobile = m
            doctor.special = s
            doctor.save()
            error = "no"
        except:
            error = "yes"
    
    d = {'doctor': doctor, 'error': error}
    return render(request, 'edit_doctor.html', d)

def Edit_Patient(request, pid):
    if not request.user.is_staff:
        return redirect('login')
    
    patient = get_object_or_404(Patient, id=pid)
    error = ""
    
    if request.method == 'POST':
        n = request.POST['name']
        m = request.POST.get('mobile', None)
        g = request.POST['gender']
        a = request.POST['address']
        try:
            patient.name = n
            patient.mobile = int(m) if m else None
            patient.gender = g
            patient.address = a
            patient.save()
            error = "no"
        except:
            error = "yes"
    
    d = {'patient': patient, 'error': error}
    return render(request, 'edit_patient.html', d)

def Edit_Appointment(request, pid):
    if not request.user.is_staff:
        return redirect('login')
    
    appointment = get_object_or_404(Appointment, id=pid)
    doctors = Doctor.objects.all()
    patients = Patient.objects.all()
    error = ""
    
    if request.method == 'POST':
        doctor_id = request.POST['doctor']
        patient_id = request.POST['patient']
        date1 = request.POST['date1']
        time1 = request.POST['time1']
        
        try:
            doctor = Doctor.objects.get(id=doctor_id)
            patient = Patient.objects.get(id=patient_id)
            
            appointment.doctor = doctor
            appointment.patient = patient
            appointment.date1 = date1
            appointment.time1 = time1
            appointment.save()
            error = "no"
        except:
            error = "yes"
    
    d = {
        'appointment': appointment,
        'doctors': doctors,
        'patients': patients,
        'error': error
    }
    return render(request, 'edit_appointment.html', d)

def contact(request):
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            email = request.POST.get('email')
            subject = request.POST.get('subject')
            message = request.POST.get('message')

            # Validate data
            if not all([name, email, subject, message]):
                return JsonResponse({
                    'success': False,
                    'message': 'Please fill in all fields.'
                })

            # Save the message
            contact_message = ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message
            )

            # Send email notification (optional)
            # You can add email sending logic here

            return JsonResponse({
                'success': True,
                'message': 'Message sent successfully!'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    return render(request, 'contact.html')
