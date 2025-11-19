import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Ticket

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to convert Mongo documents to JSON-serializable dicts

def serialize_doc(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # convert datetime to isoformat if present
    for k, v in list(d.items()):
        try:
            import datetime
            if isinstance(v, (datetime.datetime, datetime.date)):
                d[k] = v.isoformat()
        except Exception:
            pass
    return d

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

# ---------------------- Ticket CRUD API ----------------------

class TicketCreate(Ticket):
    pass

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None

@app.post("/api/tickets", response_model=dict)
def create_ticket(payload: TicketCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    ticket_id = create_document("ticket", payload)
    doc = db["ticket"].find_one({"_id": ObjectId(ticket_id)})
    return serialize_doc(doc)

@app.get("/api/tickets", response_model=List[dict])
def list_tickets(status: Optional[str] = None, priority: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    filter_q = {}
    if status:
        filter_q["status"] = status
    if priority:
        filter_q["priority"] = priority
    docs = get_documents("ticket", filter_q)
    return [serialize_doc(d) for d in docs]

@app.get("/api/tickets/{ticket_id}", response_model=dict)
def get_ticket(ticket_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        doc = db["ticket"].find_one({"_id": ObjectId(ticket_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return serialize_doc(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ticket id")

@app.patch("/api/tickets/{ticket_id}", response_model=dict)
@app.put("/api/tickets/{ticket_id}", response_model=dict)
def update_ticket(ticket_id: str, payload: TicketUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if not updates:
            doc = db["ticket"].find_one({"_id": ObjectId(ticket_id)})
            if not doc:
                raise HTTPException(status_code=404, detail="Ticket not found")
            return serialize_doc(doc)
        updates["updated_at"] = __import__('datetime').datetime.utcnow()
        result = db["ticket"].update_one({"_id": ObjectId(ticket_id)}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Ticket not found")
        doc = db["ticket"].find_one({"_id": ObjectId(ticket_id)})
        return serialize_doc(doc)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ticket id")

@app.delete("/api/tickets/{ticket_id}", response_model=dict)
def delete_ticket(ticket_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = db["ticket"].delete_one({"_id": ObjectId(ticket_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return {"status": "deleted", "id": ticket_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ticket id")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
