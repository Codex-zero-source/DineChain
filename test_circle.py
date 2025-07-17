import json, sqlite3, time
import requests

BASE_URL="http://127.0.0.1:5000"
DB_FILE="orders.db"

def insert_unpaid_order(deposit_address: str, total_cents: int=1000):
    conn=sqlite3.connect(DB_FILE)
    cur=conn.cursor()
    cur.execute("INSERT INTO orders (chat_id, platform, customer_name, summary, delivery, total, paid, deposit_address) VALUES (?,?,?,?,?,?,0,?)",
                ("test_chat","telegram","Tester","[]","Test",total_cents,deposit_address))
    order_id=cur.lastrowid
    conn.commit(); conn.close();
    return order_id

def test_circle_webhook_confirmed():
    address="0xTEST"+str(int(time.time()))
    order_id=insert_unpaid_order(address)
    payload={
        "notificationType":"AddressDeposits",
        "deposit":{
            "status":"CONFIRMED",
            "address":address,
            "amount":{"amount":"10"}
        }
    }
    r=requests.post(f"{BASE_URL}/circle/webhook",json=payload)
    assert r.status_code==200
    conn=sqlite3.connect(DB_FILE)
    cur=conn.cursor();
    cur.execute("SELECT paid FROM orders WHERE id=?",(order_id,));
    paid=cur.fetchone()[0]
    conn.close();
    assert paid==1

if __name__=="__main__":
    test_circle_webhook_confirmed()
    print("✅ Circle webhook test passed") 