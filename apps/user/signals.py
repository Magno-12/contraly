from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone

from apps.user.models import User, UserProfile, LoginAttempt, UserActivity, UserSession
from apps.core.utils import get_client_ip


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a user profile when a new user is created
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log user login activity
    """
    # Record login attempt
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    LoginAttempt.objects.create(
        email=user.email,
        ip_address=ip_address,
        user_agent=user_agent,
        successful=True,
        tenant=user.tenant
    )
    
    # Reset failed login attempts
    user.failed_login_attempts = 0
    user.last_login_ip = ip_address
    user.save(update_fields=['failed_login_attempts', 'last_login_ip'])
    
    # Create user activity
    UserActivity.objects.create(
        user=user,
        activity_type='LOGIN',
        description=f"User logged in from {ip_address}",
        ip_address=ip_address,
        user_agent=user_agent,
        module='AUTHENTICATION',
        tenant=user.tenant
    )
    
    # Create user session
    from user_agents import parse
    from datetime import timedelta
    
    # Parse user agent
    ua_string = user_agent
    try:
        user_agent_parsed = parse(ua_string)
        browser = f"{user_agent_parsed.browser.family} {user_agent_parsed.browser.version_string}"
        os = f"{user_agent_parsed.os.family} {user_agent_parsed.os.version_string}"
        device_type = 'Mobile' if user_agent_parsed.is_mobile else (
            'Tablet' if user_agent_parsed.is_tablet else (
                'Bot' if user_agent_parsed.is_bot else 'Desktop'
            )
        )
    except:
        browser = 'Unknown'
        os = 'Unknown'
        device_type = 'Unknown'
    
    # Create session with 24 hour expiry
    session_key = request.session.session_key
    expires_at = timezone.now() + timedelta(hours=24)
    
    UserSession.objects.create(
        user=user,
        session_key=session_key,
        ip_address=ip_address,
        user_agent=ua_string,
        device_type=device_type,
        browser=browser,
        os=os,
        expires_at=expires_at,
        tenant=user.tenant
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Log user logout activity
    """
    if user and request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create user activity
        UserActivity.objects.create(
            user=user,
            activity_type='LOGOUT',
            description=f"User logged out from {ip_address}",
            ip_address=ip_address,
            user_agent=user_agent,
            module='AUTHENTICATION',
            tenant=user.tenant
        )
        
        # Mark session as expired
        session_key = request.session.session_key
        if session_key:
            sessions = UserSession.objects.filter(
                user=user,
                session_key=session_key,
                is_expired=False
            )
            for session in sessions:
                session.is_expired = True
                session.logout_time = timezone.now()
                session.save()


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    """
    Log failed login attempts
    """
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Get email from credentials
        email = credentials.get('username', '')  # Username field is email in our case
        
        # Log the failed attempt
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            successful=False,
            tenant=None  # We don't know the tenant at this point
        )
        
        # Increment failed login attempts for user if they exist
        try:
            user = User.objects.get(email=email)
            user.failed_login_attempts += 1
            user.save(update_fields=['failed_login_attempts'])
            
            # TODO: If failed attempts exceed threshold, lock account or implement other security measures
        except User.DoesNotExist:
            pass  # User does not exist, nothing to update
