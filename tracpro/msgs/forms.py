from __future__ import unicode_literals

from django import forms

from .models import InboxMessage


class InboxMessageResponseForm(forms.ModelForm):

    class Meta:
        model = InboxMessage
        labels = {
            'text': 'Message text'
        }
        fields = [
            'text'
        ]

    def clean(self):
        cleaned_data = super(InboxMessageResponseForm, self).clean()
        text = cleaned_data.get("text", "").strip()

        if not text:
            raise forms.ValidationError("Please enter some message text.")

        return cleaned_data

    def __init__(self, contact, *args, **kwargs):
        self.contact = contact
        super(InboxMessageResponseForm, self).__init__(*args, **kwargs)
