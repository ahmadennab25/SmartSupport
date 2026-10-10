from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.chat.services.chat_service import EmptyMessage
from apps.customers.services.customer_service import InvalidPhoneNumber
from apps.whatsapp.services.twilio_service import build_twiml, is_valid_signature
from apps.whatsapp.services.whatsapp_service import process_incoming


@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """Twilio calls this URL for every incoming WhatsApp message; the reply is returned as TwiML."""
    if not is_valid_signature(request):
        return HttpResponseForbidden("Invalid Twilio signature.")
    if not request.POST.get("From"):
        return HttpResponseBadRequest("Missing sender.")
    try:
        reply = process_incoming(request.POST)
    except (InvalidPhoneNumber, EmptyMessage):
        return HttpResponseBadRequest("Invalid sender.")
    return HttpResponse(build_twiml(reply), content_type="application/xml; charset=utf-8")
