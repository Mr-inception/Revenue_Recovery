"""
Step 1 sanity check: confirm Razorpay test-mode keys work.
Run: python 00_test_connection.py
"""
import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import razorpay

KEY_ID = "rzp_test_TSK03hs97FXyMc"      # paste your key_id
KEY_SECRET = "1dfDDAxi8N60vDvDCy0rD7WZ"  # paste your key_secret

client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

# Create a test payment link - this is literally your recovery action later
payment_link = client.payment_link.create({
    "amount": 50000,  # in paise = ₹500
    "currency": "INR",
    "description": "Test recovery link",
    "customer": {
        "name": "Test Customer",
        "email": "test@example.com",
        "contact": "+919876543210"
    },
    "notify": {"sms": False, "email": False},
})

print("✅ Connection works.")
print("Payment Link ID:", payment_link["id"])
print("Short URL:", payment_link["short_url"])
print("Status:", payment_link["status"])