import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MayaCollectionsBot")

app = FastAPI(
    title="Kapture Finance Collections Webhook Server",
    description="Mock backend to handle Vapi tool calls and send SMS notifications for loan collection voicebot 'Maya'."
)

# Mock database
CUSTOMER_DB = {
    "CUST_9988": {
        "name": "Rahul Sharma",
        "phone": "+919876543210",
        "aadhaar_last_4": "1234",
        "overdue_amount": 8499.00,
        "days_past_due": 12,
        "loan_type": "Personal Loan",
        "disposition": None,
        "ptp_date": None,
        "notes": ""
    }
}

# --- Request Models ---
class VerifyRequest(BaseModel):
    customer_id: str
    verification_type: str
    verification_value: str

class LogPTPRequest(BaseModel):
    customer_id: str
    ptp_date: str
    ptp_amount: float

class SendLinkRequest(BaseModel):
    customer_id: str
    amount: float
    channel: str

class MarkDispositionRequest(BaseModel):
    customer_id: str
    disposition: str
    notes: Optional[str] = ""

class EscalateRequest(BaseModel):
    reason: str


# --- Core Helper Functions ---
def execute_verify(customer_id: str, v_type: str, v_value: str) -> Dict[str, Any]:
    logger.info(f"Executing Verification: customer_id={customer_id}, type={v_type}, value={v_value}")
    if customer_id not in CUSTOMER_DB:
        return {"status": "FAILED", "message": "Customer ID not found."}
    
    customer = CUSTOMER_DB[customer_id]
    if v_type == "aadhaar_last_4":
        if v_value == customer["aadhaar_last_4"]:
            return {
                "status": "VERIFIED",
                "message": "Identity successfully verified.",
                "customer_name": customer["name"]
            }
        else:
            return {"status": "FAILED", "message": "Incorrect Aadhaar digits."}
    return {"status": "FAILED", "message": f"Unsupported verification type: {v_type}"}


def execute_log_ptp(customer_id: str, ptp_date: str, ptp_amount: float) -> Dict[str, Any]:
    logger.info(f"Executing Log PTP: customer_id={customer_id}, date={ptp_date}, amount={ptp_amount}")
    if customer_id not in CUSTOMER_DB:
        return {"status": "FAILED", "message": "Customer ID not found."}
    
    # Simple validation of PTP date (within 3 days)
    try:
        ptp_dt = datetime.strptime(ptp_date, "%Y-%m-%d").date()
        today = datetime.now().date()
        days_diff = (ptp_dt - today).days
        if days_diff < 0:
            return {"status": "REJECTED", "message": "PTP date cannot be in the past."}
        if days_diff > 3:
            return {"status": "REJECTED", "message": "PTP date exceeds the policy limit of 3 days."}
    except ValueError:
        pass  # If relative string passed instead of ISO date, skip parsing validation but log it
        
    CUSTOMER_DB[customer_id]["ptp_date"] = ptp_date
    CUSTOMER_DB[customer_id]["disposition"] = "PTP_COLLECTED"
    
    return {
        "status": "SUCCESS",
        "ptp_id": "PTP_MOCK_" + str(int(datetime.now().timestamp())),
        "message": f"Promise to pay logged for {ptp_date} for amount INR {ptp_amount}."
    }


def send_sms_via_twilio(to_phone: str, message_body: str) -> bool:
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    
    if not (account_sid and auth_token and from_number):
        logger.info("[SMS SIMULATION] Twilio env vars missing. Skipping real SMS sending.")
        return False

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=to_phone
        )
        logger.info(f"[SMS SENT] Twilio Message SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"[SMS ERROR] Failed to send SMS via Twilio: {str(e)}")
        return False


def execute_send_payment_link(customer_id: str, amount: float, channel: str) -> Dict[str, Any]:
    logger.info(f"Executing Send Payment Link: customer_id={customer_id}, amount={amount}, channel={channel}")
    if customer_id not in CUSTOMER_DB:
        return {"status": "FAILED", "message": "Customer ID not found."}
    
    customer = CUSTOMER_DB[customer_id]
    phone = customer["phone"]
    payment_url = f"https://pay.kapturefinance.co.in/pay?id={customer_id}&amt={amount}"
    
    sms_body = f"Dear {customer['name']}, your Kapture Finance Personal Loan EMI of INR {amount:.2f} is overdue. Please pay immediately via this secure link: {payment_url}"
    
    # Attempt real SMS sending via Twilio, fallback to simulated
    sent_real = send_sms_via_twilio(phone, sms_body)
    
    logger.info(f"[NOTIFICATION TRIGGERED] Channel={channel} to Phone={phone}")
    logger.info(f"[SMS BODY] {sms_body}")
    
    return {
        "status": "SENT",
        "channel": channel,
        "sent_to": phone,
        "is_simulated": not sent_real,
        "message": f"Payment link generated and sent to {phone} via {channel}."
    }


def execute_mark_disposition(customer_id: str, disposition: str, notes: str) -> Dict[str, Any]:
    logger.info(f"Executing Mark Disposition: customer_id={customer_id}, disposition={disposition}, notes={notes}")
    if customer_id not in CUSTOMER_DB:
        return {"status": "FAILED", "message": "Customer ID not found."}
    
    CUSTOMER_DB[customer_id]["disposition"] = disposition
    CUSTOMER_DB[customer_id]["notes"] = notes
    
    return {
        "status": "LOGGED",
        "message": f"Call disposition '{disposition}' saved for customer {customer_id}."
    }


@app.get("/")
def read_root():
    return {"message": "Kapture Finance Webhook Server is running successfully!"}

@app.get("/webhook")
def get_webhook():
    return {"message": "Webhook endpoint is active. Send POST requests here from Vapi!"}


# --- API Endpoints (Direct REST) ---

@app.post("/verify_customer")
def api_verify_customer(req: VerifyRequest):
    return execute_verify(req.customer_id, req.verification_type, req.verification_value)

@app.post("/log_promise_to_pay")
def api_log_ptp(req: LogPTPRequest):
    res = execute_log_ptp(req.customer_id, req.ptp_date, req.ptp_amount)
    if res["status"] == "REJECTED":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.post("/send_payment_link")
def api_send_payment_link(req: SendLinkRequest):
    return execute_send_payment_link(req.customer_id, req.amount, req.channel)

@app.post("/mark_disposition")
def api_mark_disposition(req: MarkDispositionRequest):
    return execute_mark_disposition(req.customer_id, req.disposition, req.notes)

@app.post("/escalate_to_agent")
def api_escalate(req: EscalateRequest):
    logger.info(f"Call escalated to human agent. Reason: {req.reason}")
    return {"status": "ESCALATED", "message": "Routing call to nearest available agent."}


# --- Unified Vapi Webhook Endpoint ---
# Vapi sends a POST request here if you define this URL as the assistant's Webhook / Server URL
@app.post("/webhook")
async def vapi_webhook(request: Request):
    payload = await request.json()
    logger.info(f"Received Vapi Webhook event payload: {payload}")
    
    # Check if this is a tool-calls request
    message = payload.get("message", {})
    msg_type = message.get("type")
    
    if msg_type == "tool-calls":
        tool_calls = message.get("toolCalls", [])
        results = []
        
        for call in tool_calls:
            call_id = call.get("id")
            function_info = call.get("function", {})
            name = function_info.get("name")
            args = function_info.get("arguments", {})
            
            logger.info(f"Processing Vapi tool call: ID={call_id}, name={name}, args={args}")
            
            result_payload = {}
            try:
                if name == "verify_customer":
                    result_payload = execute_verify(
                        customer_id=args.get("customer_id"),
                        v_type=args.get("verification_type"),
                        v_value=args.get("verification_value")
                    )
                elif name == "log_promise_to_pay":
                    result_payload = execute_log_ptp(
                        customer_id=args.get("customer_id"),
                        ptp_date=args.get("ptp_date"),
                        ptp_amount=args.get("ptp_amount", 8499.00)
                    )
                elif name == "send_payment_link":
                    result_payload = execute_send_payment_link(
                        customer_id=args.get("customer_id"),
                        amount=args.get("amount", 8499.00),
                        channel=args.get("channel", "SMS")
                    )
                elif name == "escalate_to_agent":
                    result_payload = {"status": "ESCALATED", "message": "Connecting call to live agent."}
                elif name == "mark_disposition":
                    result_payload = execute_mark_disposition(
                        customer_id=args.get("customer_id"),
                        disposition=args.get("disposition"),
                        notes=args.get("notes", "")
                    )
                else:
                    result_payload = {"status": "ERROR", "message": f"Unknown tool name: {name}"}
            except Exception as e:
                logger.error(f"Error executing tool {name}: {str(e)}")
                result_payload = {"status": "ERROR", "message": str(e)}
                
            results.append({
                "toolCallId": call_id,
                "result": result_payload
            })
            
        return {"results": results}
    
    # Handle other Vapi message types (e.g. status-update, end-of-call-report)
    elif msg_type == "end-of-call-report":
        logger.info("Call completed. Received End of Call Report.")
        # We can extract final duration, recording URL, transcription, etc.
        
    return {"status": "received"}


if __name__ == "__main__":
    import uvicorn
    # Run uvicorn on port 8000
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
