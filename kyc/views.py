from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.decorators import login_required
import json
import os
import cv2
import numpy as np
import base64
from datetime import datetime, timezone
import subprocess
import time
from .models import VerificationSession, Tenant, Customer, VerificationLink
from accounts.models import User
from django import forms
from django.utils import timezone as dj_timezone
from datetime import timedelta
from django.conf import settings as django_settings
from django.core.mail import send_mail

# Global variable to track liveness process
liveness_process = None


def index(request):
    """Render the main KYC verification page"""
    return render(request, 'kyc/index.html')


def liveness_page(request):
    """Render the liveness detection page"""
    return render(request, 'kyc/liveness.html')


def _role_denied():
    return HttpResponseForbidden("Access denied")


def _require_user_type(user, allowed_types):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return "super_admin" in allowed_types
    return user.role in allowed_types


@login_required
def platform_dashboard(request):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()

    tenants = Tenant.objects.all().order_by("name")
    context = {
        "tenants": tenants,
        "tenant_count": tenants.count(),
        "user_count": User.objects.count(),
        "session_count": VerificationSession.objects.count(),
        "pending_reviews": VerificationSession.objects.filter(review_status="pending").count(),
    }
    return render(request, "kyc/platform_dashboard.html", context)


@login_required
def tenant_dashboard(request):
    if not _require_user_type(request.user, {"owner", "admin", "staff"}):
        return _role_denied()
    if not request.user.tenant:
        return HttpResponseForbidden("No tenant assigned")

    tenant = request.user.tenant
    sessions = VerificationSession.objects.filter(tenant=tenant).order_by("-created_at")[:200]
    latest_link = None

    if request.method == "POST" and request.POST.get("action") == "create_customer":
        customer_form = CustomerCreateForm(request.POST)
        if customer_form.is_valid():
            customer = Customer.objects.create(
                tenant=tenant,
                full_name=customer_form.cleaned_data["full_name"],
                email=customer_form.cleaned_data["email"] or None,
                phone=customer_form.cleaned_data["phone"] or None,
                external_ref=customer_form.cleaned_data["external_ref"] or None,
            )
            expires_at = dj_timezone.now() + timedelta(days=2)
            latest_link = VerificationLink.objects.create(
                tenant=tenant,
                customer=customer,
                expires_at=expires_at,
            )
            if customer.email:
                link_url = ""
                public_base = getattr(django_settings, "PUBLIC_BASE_URL", "").rstrip("/")
                if public_base:
                    link_url = f"{public_base}/verify/start/{latest_link.token}/"
                else:
                    link_url = f"{request.scheme}://{request.get_host()}/verify/start/{latest_link.token}/"

                send_mail(
                    subject="Your KYC Verification",
                    message=(
                        f"Hello {customer.full_name},\n\n"
                        f"Please complete your verification using this link:\n{link_url}\n\n"
                        "This link expires in 48 hours."
                    ),
                    from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[customer.email],
                    fail_silently=True,
                )
    else:
        customer_form = CustomerCreateForm()

    context = {
        "tenant": tenant,
        "sessions": sessions,
        "session_count": VerificationSession.objects.filter(tenant=tenant).count(),
        "pending_reviews": VerificationSession.objects.filter(tenant=tenant, review_status="pending").count(),
        "customer_form": customer_form,
        "latest_link": latest_link,
        "public_base_url": getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/"),
    }
    return render(request, "kyc/tenant_dashboard.html", context)


class StaffCreateForm(forms.Form):
    email = forms.EmailField()
    role = forms.ChoiceField(choices=[("owner", "Owner"), ("admin", "Admin"), ("staff", "Staff")])
    password = forms.CharField(widget=forms.PasswordInput)


class CustomerCreateForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False)
    external_ref = forms.CharField(required=False)


@login_required
def tenant_team(request):
    if not _require_user_type(request.user, {"owner", "admin"}):
        return _role_denied()
    if not request.user.tenant:
        return HttpResponseForbidden("No tenant assigned")

    tenant = request.user.tenant
    staff_qs = User.objects.filter(tenant=tenant).order_by("role", "email")

    if request.method == "POST":
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data["role"]
            if role == "owner" and request.user.role != "owner":
                return HttpResponseForbidden("Only owners can create other owners.")
            User.objects.create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                role=role,
                tenant=tenant,
                is_staff=True,
            )
            return redirect("tenant_team")
    else:
        form = StaffCreateForm()

    context = {
        "tenant": tenant,
        "staff": staff_qs,
        "form": form,
    }
    return render(request, "kyc/tenant_team.html", context)


@login_required
def customer_start(request):
    if request.method == "POST":
        company_id = request.POST.get("company_id")
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")

        if not company_id or not full_name:
            return render(request, "kyc/customer_start.html", {"error": "Company ID and name are required."})

        try:
            tenant = Tenant.objects.get(slug=company_id)
        except Tenant.DoesNotExist:
            return render(request, "kyc/customer_start.html", {"error": "Company ID not found."})

        customer = Customer.objects.create(
            tenant=tenant,
            full_name=full_name,
            email=email or None,
            phone=phone or None,
        )

        return redirect(f"/verify/?tenant_slug={tenant.slug}&customer_id={customer.id}")

    return render(request, "kyc/customer_start.html")


def customer_verify(request):
    tenant_slug = request.GET.get("tenant_slug")
    customer_id = request.GET.get("customer_id")
    if not tenant_slug or not customer_id:
        return redirect("/customer/start/")
    return render(request, "kyc/index.html", {"tenant_slug": tenant_slug, "customer_id": customer_id})


def verify_link(request, token):
    try:
        link = VerificationLink.objects.select_related("tenant", "customer").get(token=token)
    except VerificationLink.DoesNotExist:
        return HttpResponseForbidden("Invalid or expired link")

    if link.expires_at and link.expires_at < dj_timezone.now():
        return HttpResponseForbidden("Link expired")

    return redirect(f"/verify/?tenant_slug={link.tenant.slug}&customer_id={link.customer.id}")


@login_required
def review_sessions(request):
    tenant_slug = request.GET.get("tenant")
    status = request.GET.get("status")
    review_status = request.GET.get("review_status")

    if not _require_user_type(request.user, {"super_admin", "owner", "admin", "staff"}):
        return _role_denied()

    qs = VerificationSession.objects.select_related("tenant", "reviewed_by", "customer").order_by("-created_at")

    user_tenant = _get_user_tenant(request.user)
    if not request.user.is_superuser:
        if user_tenant is None:
            return HttpResponseForbidden("No tenant membership")
        qs = qs.filter(tenant=user_tenant)
    elif tenant_slug:
        qs = qs.filter(tenant__slug=tenant_slug)

    if status:
        qs = qs.filter(status=status)
    if review_status:
        qs = qs.filter(review_status=review_status)

    context = {
        "sessions": qs[:200],
        "tenant_slug": tenant_slug or "",
        "status": status or "",
        "review_status": review_status or "",
        "is_superuser": request.user.is_superuser,
        "user_tenant": user_tenant,
    }
    return render(request, "kyc/admin_sessions.html", context)


@login_required
def review_session_detail(request, session_id):
    session = get_object_or_404(
        VerificationSession.objects.select_related("tenant", "reviewed_by", "customer"), id=session_id
    )

    if not _require_user_type(request.user, {"super_admin", "owner", "admin", "staff"}):
        return _role_denied()

    user_tenant = _get_user_tenant(request.user)
    if not request.user.is_superuser:
        if user_tenant is None:
            return HttpResponseForbidden("No tenant membership")
        if session.tenant_id != user_tenant.id:
            return HttpResponseForbidden("Access denied for tenant")

    if request.method == "POST":
        session.review_status = request.POST.get("review_status", session.review_status)
        session.review_notes = request.POST.get("review_notes", session.review_notes)
        session.reviewed_by = request.user
        session.reviewed_at = datetime.now(timezone.utc)
        session.save(update_fields=["review_status", "review_notes", "reviewed_by", "reviewed_at"])
        return redirect("review_session_detail", session_id=session.id)

    context = {
        "session": session,
        "customer": session.customer,
        "front_url": _media_url(session.document_front_url or session.front_image),
        "back_url": _media_url(session.document_back_url or session.back_image),
        "selfie_url": _media_url(session.selfie_url or session.selfie_image),
    }
    return render(request, "kyc/admin_session_detail.html", context)


@csrf_exempt
def start_liveness(request):
    """
    Marks liveness as started for the session.
    Endpoint: /start-liveness/
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body or "{}")
            session_id = data.get("session_id")

            if session_id:
                try:
                    session = VerificationSession.objects.get(id=session_id)
                    session.liveness_running = True
                    session.updated_at = datetime.now(timezone.utc)
                    session.save(update_fields=["liveness_running", "updated_at"])
                except VerificationSession.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Session not found'
                    }, status=404)

            return JsonResponse({
                'success': True,
                'message': 'Liveness detection started'
            })

        except Exception as e:
            print(f"❌ Error starting liveness: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Failed to start liveness detection: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method. Use POST.'
    }, status=405)


@csrf_exempt
def check_liveness(request):
    """
    Polls for liveness detection results
    Endpoint: /check-liveness/
    """
    try:
        result_file = 'liveness_result.json'

        # Check if the result file exists
        if os.path.exists(result_file):
            print(f"✓ Found liveness result file")

            # Read the result
            with open(result_file, 'r') as f:
                result = json.load(f)

            print(f"Liveness result: {result}")

            # Clean up the file after reading
            try:
                os.remove(result_file)
                print("✓ Liveness result file cleaned up")
            except Exception as e:
                print(f"⚠️ Could not remove result file: {e}")

            return JsonResponse({
                'completed': True,
                'verified': result.get('verified', False),
                'confidence': result.get('confidence', 0),
                'challenges': result.get('challenges', {}),
                'timestamp': result.get('timestamp', time.time())
            })
        else:
            # Still processing
            return JsonResponse({
                'completed': False,
                'message': 'Liveness detection in progress...'
            })

    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {str(e)}")
        return JsonResponse({
            'completed': False,
            'error': f'Invalid JSON in result file: {str(e)}'
        }, status=500)

    except Exception as e:
        print(f"❌ Error checking liveness: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'completed': False,
            'error': f'Failed to check liveness status: {str(e)}'
        }, status=500)


@csrf_exempt
def cancel_liveness(request):
    """
    Cancels the running liveness detection process
    Endpoint: /cancel-liveness/
    """
    global liveness_process

    if request.method == 'POST':
        try:
            # Terminate the process if it's running
            if liveness_process and liveness_process.poll() is None:
                liveness_process.terminate()
                try:
                    liveness_process.wait(timeout=5)
                    print("✓ Liveness process terminated gracefully")
                except subprocess.TimeoutExpired:
                    liveness_process.kill()
                    print("⚠️ Liveness process killed forcefully")
            else:
                print("⚠️ No active liveness process to cancel")

            # Clean up result file
            result_file = 'liveness_result.json'
            if os.path.exists(result_file):
                os.remove(result_file)
                print("✓ Cleaned up liveness result file")

            return JsonResponse({
                'success': True,
                'message': 'Liveness detection cancelled'
            })

        except Exception as e:
            print(f"❌ Error cancelling liveness: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to cancel liveness: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method. Use POST.'
    }, status=405)


@csrf_exempt
def capture_document(request):
    """Handle document capture from camera"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image')
            doc_type = data.get('type')

            if not image_data or not doc_type:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing image data or document type'
                }, status=400)

            # Decode base64 image
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)

            # Convert to numpy array for OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Basic quality checks
            quality_check = check_image_quality(img)
            if not quality_check['passed']:
                return JsonResponse({
                    'success': False,
                    'error': quality_check['message']
                }, status=400)

            # Save image
            os.makedirs('documents/captured', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"documents/captured/{doc_type}_{timestamp}.jpg"

            # Save with higher quality for better face detection
            cv2.imwrite(filename, img, [cv2.IMWRITE_JPEG_QUALITY, 95])

            print(f"✓ Saved {doc_type}: {filename}")

            return JsonResponse({
                'success': True,
                'filename': filename,
                'type': doc_type,
                'quality': quality_check
            })

        except Exception as e:
            print(f"❌ Capture error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only POST requests allowed'}, status=400)


@csrf_exempt
def verify_kyc(request):
    """Process complete KYC verification"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
            tenant = _resolve_tenant(data)
            front_path = data.get('front_image')
            back_path = data.get('back_image')
            selfie_path = data.get('selfie_image')
            liveness_verified = data.get('liveness_verified', False)  # NEW: Get liveness status

            print(f"\n{'=' * 70}")
            print("Starting KYC Verification...")
            print(f"Front: {front_path}")
            print(f"Back: {back_path}")
            print(f"Selfie: {selfie_path}")
            print(f"Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
            print(f"{'=' * 70}\n")

            if session_id and tenant is None:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing or invalid tenant'
                }, status=400)

            if not front_path or not selfie_path:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required images (front and selfie)'
                }, status=400)

            # Check if files exist
            front_path = _resolve_media_path(front_path)
            back_path = _resolve_media_path(back_path)
            selfie_path = _resolve_media_path(selfie_path)

            if not os.path.exists(front_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Front image not found: {front_path}'
                }, status=400)

            if not os.path.exists(selfie_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Selfie image not found: {selfie_path}'
                }, status=400)

            # Import DeepFace here
            from deepface import DeepFace

            print("Step 1: Extracting face from ID card...")

            # Extract face from ID card
            try:
                faces = DeepFace.extract_faces(
                    img_path=front_path,
                    detector_backend='opencv',
                    enforce_detection=False,
                    align=True
                )

                if not faces or len(faces) == 0:
                    print("❌ No face detected in ID card")
                    return JsonResponse({
                        'success': False,
                        'error': 'No face found in ID card. Please ensure the photo on the ID is clear and visible.'
                    }, status=400)

                print(f"✓ Found {len(faces)} face(s) in ID")

                # Get the largest face
                largest_face = max(faces, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])

                # Save extracted face
                doc_image = cv2.imread(front_path)
                facial_area = largest_face['facial_area']
                x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']

                # Add padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(doc_image.shape[1] - x, w + 2 * padding)
                h = min(doc_image.shape[0] - y, h + 2 * padding)

                id_face = doc_image[y:y + h, x:x + w]

                # Save ID face
                os.makedirs('documents/extracted_faces', exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                id_face_path = f"documents/extracted_faces/id_face_{timestamp}.jpg"
                cv2.imwrite(id_face_path, id_face, [cv2.IMWRITE_JPEG_QUALITY, 95])

                print(f"✓ Extracted ID face: {id_face_path}")

            except Exception as e:
                print(f"❌ Face extraction failed: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Could not extract face from ID: {str(e)}'
                }, status=400)

            print("\nStep 2: Comparing faces...")

            # Compare faces
            try:
                models = ["VGG-Face", "Facenet"]
                results = []

                for model in models:
                    print(f"Running {model}...")
                    result = DeepFace.verify(
                        img1_path=id_face_path,
                        img2_path=selfie_path,
                        model_name=model,
                        enforce_detection=False
                    )

                    distance = result['distance']
                    similarity = (1 - distance) * 100
                    verified = result['verified']

                    results.append({
                        'model': model,
                        'similarity': similarity,
                        'verified': verified,
                        'distance': distance
                    })

                    status = "✓ MATCH" if verified else "✗ NO MATCH"
                    print(f"  {model}: {similarity:.1f}% - {status}")

                # Calculate final decision
                votes_yes = sum(1 for r in results if r['verified'])
                avg_similarity = sum(r['similarity'] for r in results) / len(results)
                final_match = votes_yes >= 1  # At least 1 model says match

                print(f"\n{'=' * 70}")
                print(f"VERIFICATION RESULT:")
                print(f"  Average Similarity: {avg_similarity:.1f}%")
                print(f"  Models Agree: {votes_yes}/{len(results)}")
                print(f"  Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
                print(f"  Final Decision: {'✅ VERIFIED' if final_match else '❌ REJECTED'}")
                print(f"{'=' * 70}\n")

                result_payload = {
                    'success': True,
                    'verified': final_match,
                    'similarity': avg_similarity,
                    'confidence': avg_similarity,
                    'votes': votes_yes,
                    'total_models': len(results),
                    'liveness_verified': liveness_verified,  # NEW: Include liveness status
                    'details': {
                        'id_face_path': id_face_path,
                        'models': results,
                        'liveness_status': 'verified' if liveness_verified else 'skipped'
                    }
                }

                if session_id:
                    _update_session_verification(
                        session_id=session_id,
                        tenant=tenant,
                        verified=final_match,
                        confidence=avg_similarity,
                        similarity=avg_similarity,
                        liveness_verified=liveness_verified,
                    )

                return JsonResponse(result_payload)

            except Exception as e:
                print(f"❌ Face comparison failed: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Face comparison failed: {str(e)}'
                }, status=500)

        except Exception as e:
            print(f"❌ Verification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only POST requests allowed'}, status=400)


def _resolve_media_path(path_or_name):
    if not path_or_name:
        return path_or_name
    if os.path.exists(path_or_name):
        return path_or_name
    return os.path.join(settings.MEDIA_ROOT, path_or_name)


def _media_url(filename):
    if not filename:
        return ""
    return f"{settings.MEDIA_URL}{filename}"


def _get_user_tenant(user):
    if not user.is_authenticated:
        return None
    return user.tenant


def _update_session_verification(session_id, tenant, verified, confidence, similarity, liveness_verified):
    try:
        if tenant is None:
            return
        session = VerificationSession.objects.get(id=session_id, tenant=tenant)
    except VerificationSession.DoesNotExist:
        return

    session.verify_verified = bool(verified)
    session.verify_confidence = float(confidence or 0)
    session.verify_similarity = float(similarity or 0)
    session.liveness_verified = bool(liveness_verified)
    session.updated_at = datetime.now(timezone.utc)
    session.save(update_fields=[
        "verify_verified",
        "verify_confidence",
        "verify_similarity",
        "liveness_verified",
        "updated_at",
    ])


def _resolve_tenant(data):
    tenant_id = data.get("tenant_id")
    tenant_slug = data.get("tenant_slug")
    if not tenant_id and not tenant_slug:
        return None
    try:
        if tenant_id:
            return Tenant.objects.get(id=tenant_id)
        return Tenant.objects.get(slug=tenant_slug)
    except Tenant.DoesNotExist:
        return None


def check_image_quality(img):
    """Check if image quality is acceptable"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)

    if brightness < 40:
        return {
            'passed': False,
            'message': 'Image too dark. Please ensure good lighting.',
            'brightness': float(brightness)
        }

    if brightness > 220:
        return {
            'passed': False,
            'message': 'Image too bright. Reduce lighting or avoid glare.',
            'brightness': float(brightness)
        }

    # Check for blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    if laplacian_var < 50:  # Lowered threshold for mobile cameras
        return {
            'passed': False,
            'message': 'Image is blurry. Please hold steady and focus.',
            'sharpness': float(laplacian_var)
        }

    return {
        'passed': True,
        'message': 'Image quality is good',
        'brightness': float(brightness),
        'sharpness': float(laplacian_var)
    }
