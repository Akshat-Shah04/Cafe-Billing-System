from django.http import JsonResponse


def form_errors(form, status=400):
    """Field errors as {"field": "first message"}, plus "__all__" for form-wide ones."""
    errors = {field: [str(e) for e in errs][0] for field, errs in form.errors.items()}
    return JsonResponse({"ok": False, "errors": errors}, status=status)


def error(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def ok(**data):
    return JsonResponse({"ok": True, **data})
