# Customization

How to shape the kit for a real engagement.

## Swap the catalog

The bundled `default_catalog()` is generic B2B SaaS. For your
engagement, replace it entirely:

```python
from email_triage.catalog import Catalog, EmailClass
from email_triage.classifier import Classifier

my_catalog = Catalog(classes=[
    EmailClass(
        name="appointment_request",
        queue="scheduling",
        sla_hours=2,
        keywords=["schedule", "appointment", "book a time",
                  "availability", "reschedule"],
        drafts_reply=True,
        description="Inbound request to schedule or reschedule.",
    ),
    EmailClass(
        name="insurance_claim",
        queue="claims_intake",
        sla_hours=12,
        keywords=["claim", "policy number", "incident", "date of loss"],
        drafts_reply=False,
        description="New insurance claim filing.",
    ),
    # ... etc
])

clf = Classifier(catalog=my_catalog, internal_domains=["yourcompany.com"])
```

Add per-class reply templates (`prompts/appointment_request.txt`) for
the classes where `drafts_reply=True`. That's all the wiring needed.

## Add a single class

Edit `src/email_triage/catalog.py::default_catalog`:

```python
EmailClass(
    name="cancellation",
    queue="retention_team",
    sla_hours=2,           # responding fast matters for retention
    keywords=["cancel", "cancel my subscription", "downgrade",
              "stop billing", "no longer need"],
    drafts_reply=True,
    description="Customer is cancelling; retention team should respond fast.",
),
```

Create `prompts/cancellation.txt` if `drafts_reply=True`. Add an EML
fixture + classification case + draft case in `evals/`. Run the
harness to confirm nothing else broke.

## Add a new reply template

Templates live in `prompts/<class_name>.txt`. They're Python
`str.format` templates with three vars available:

- `{sender_name}` — first name (or "there" if no name parsed)
- `{subject}` — the original email's subject line
- `{body_excerpt}` — first ~200 chars of the original body

Example:

```text
Hi {sender_name},

Thanks for reaching out about "{subject}". I'll loop in [Owner] who
handles this. They typically respond within {sla} hours.

Best,
[Auto-reply, ticket {ticket_id}]
```

For variables beyond the three built-in ones, extend
`Drafter._draft_substitution` to compute them.

## Tune the review threshold

```python
clf = Classifier(review_threshold=0.6)  # stricter - more emails to human review
clf = Classifier(review_threshold=0.3)  # looser - more autonomous routing
```

How to pick: process ~200 real emails through the classifier, plot the
confidence histogram, set the threshold at the natural gap.

## Improve a class that misclassifies

1. **Add more keywords** — open the failing fixture, see what
   distinguishing words the classifier missed, add them to the class
   in the catalog.
2. **Add a distinguishing keyword to a competing class** — sometimes
   easier than making the right class win.
3. **Lock the fix with a fixture** — drop the failing email into
   `fixtures/<class>-<id>.eml` and add it to `evals/classification.json`
   so the regression can't come back.

## Swap to LLM-based drafting (just for hard cases)

Hybrid pattern: substitution by default, LLM fallback when the rules
classifier had low-ish confidence:

```python
class HybridDrafter(Drafter):
    def __init__(self, *args, llm_confidence_floor=0.6, **kwargs):
        super().__init__(*args, **kwargs)
        self.llm_floor = llm_confidence_floor

    def draft_with_routing(self, email, decision):
        # Use LLM only when classification was uncertain
        if decision.confidence < self.llm_floor:
            self.backend = "claude"
        return self.draft(email, decision.label)
```

You get substitution speed + LLM nuance only when you need it.

## Wire to Gmail

```python
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import base64

from email_triage.parser import parse_eml_bytes
from email_triage.classifier import Classifier, route
from email_triage.drafter import Drafter

creds = Credentials.from_authorized_user_file('token.json')
gmail = build('gmail', 'v1', credentials=creds)

clf = Classifier(internal_domains=["yourcompany.com"])
drafter = Drafter()

# Pull unread messages
results = gmail.users().messages().list(userId='me', q='is:unread').execute()
for msg_ref in results.get('messages', []):
    raw = gmail.users().messages().get(
        userId='me', id=msg_ref['id'], format='raw'
    ).execute()
    mime_bytes = base64.urlsafe_b64decode(raw['raw'])
    email_obj = parse_eml_bytes(mime_bytes)

    result = clf.classify(email_obj)
    decision = route(result, clf.catalog)

    if decision.drafts_reply:
        draft = drafter.draft(email_obj, decision.label)
        # Save as Gmail draft for human review
        gmail.users().drafts().create(userId='me', body={
            'message': {
                'raw': base64.urlsafe_b64encode(
                    f"To: {email_obj.sender_email}\nSubject: {draft.subject}\n\n{draft.body}".encode()
                ).decode()
            }
        }).execute()

    # Label the message based on routing decision
    label_id = ensure_gmail_label(decision.queue)
    gmail.users().messages().modify(
        userId='me', id=msg_ref['id'],
        body={'addLabelIds': [label_id]}
    ).execute()
```

## Wire to Microsoft 365 / Outlook

```python
from email_triage.parser import parse_eml_bytes
from email_triage.classifier import Classifier, route

# Using msgraph-sdk-python
async for msg in graph_client.me.messages.get_async(top=100):
    # Get MIME content for this message
    mime_response = await graph_client.me.messages.by_message_id(msg.id).value.get_async()
    email_obj = parse_eml_bytes(mime_response)

    result = clf.classify(email_obj)
    decision = route(result, clf.catalog)
    # ... your handling
```

## Persist triage history for analytics

Every triage decision is data:

```python
import json, time
from dataclasses import asdict

def persist(email_obj, result, decision, draft):
    record = {
        "ts": time.time(),
        "message_id": email_obj.message_id,
        "from": email_obj.sender_email,
        "subject": email_obj.subject,
        "label": result.label,
        "confidence": result.confidence,
        "queue": decision.queue,
        "review_required": decision.review_required,
        "drafted": draft is not None,
    }
    cosmos.upsert_item(record)
```

Later you can compute: which classes get most human-review? Where is
the threshold too tight? Which sender domains never match anything?

## Use prompt-registry-kit for templates

If you want versioned + eval-gated reply templates (instead of
just-files-on-disk), point the drafter at a
[prompt-registry-kit](https://github.com/derekgallardo01/prompt-registry-kit)
registry:

```python
from prompt_registry.registry import Registry as PromptReg

prompt_reg = PromptReg("./prompt-registry")

def draft_via_registry(email, class_name):
    template_version = prompt_reg.get(f"reply_{class_name}").active()
    template = template_version.template
    # ... same substitution logic
```

Now your reply templates have versioning, A/B testing, and golden
eval cases too.
