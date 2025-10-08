from collections import defaultdict

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import Loan

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass


@shared_task
def check_overdue_loans():
    current_date = timezone.now().date()
    overdue_loans = Loan.objects.select_related("member", "book", "member__user").filter(
        is_returned=False,
        due_date__lt=current_date
    )

    over_due_loans_member_dict = defaultdict(list)
    for loan in overdue_loans:
        over_due_loans_member_dict[loan.member.user.email].append(loan)

    for email, loans in over_due_loans_member_dict.items():
        titles =  [loan.book.title for loan in loans]
        book_titles_str = ", ".join(titles)
        send_mail(
            subject='Overdue Loan/s Reminder',
            message=f'Hello {loan.member.user.username},\n\nYou are reminded about the over due loan books mentioned here "{book_titles_str}".\nPlease return the book/s',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

