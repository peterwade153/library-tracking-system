from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, ExtendLoanSerializer
from rest_framework.decorators import action
from django.utils import timezone
from django.db.models import Q, Count
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author").all()
    serializer_class = BookSerializer

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    # @action(detail=False, methods=["get"])
    # def top_active(self, request, pk=None):
    #     now = timezone.now().date()
    #     top_members = Member.objects.select_related().annotate(
    #         active_loans=Count("loans", 
    #             filter = Q("loan__is_returned"=False)
    #         ).orderby("-active_loans")[:5]
    #     )



class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=["post"])
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()
        if loan.is_returned:
            return Response({'error': 'Loan nolonger active'}, status=status.HTTP_400_BAD_REQUEST)
        
        current_date = timezone.now().date()
        if loan.due_date < current_date:
            return Response({'error': 'Loan is overdue'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ExtendLoanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        additional_days = serializer.validated_data["additional_days"]
        loan.due_date = loan.due_date + timezone.timedelta(days=additional_days)
        loan.save()
        return Response(
            {
                "id": loan.id,
                "due_date": loan.due_date
            }, 
            status=status.HTTP_200_OK
        )
