import streamlit as st
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date

# Set page config
st.set_page_config(page_title="Salon Executive Management", layout="wide", page_icon="✂️")

# Database Connection Helper (with connection timeout)
import ssl

def get_connection():
    # Standard CA bundle location on Debian/Ubuntu (used by Streamlit Cloud)
    ca_path = "/etc/ssl/certs/ca-certificates.crt"
    
    cnx_kwargs = {
        "host": "gateway01.ap-northeast-1.prod.aws.tidbcloud.com",
        "port": 4000,
        "user": "3FJFTp8drNUbUPy.root",      # e.g., xxxxxx.root
        "password": "lQEcpuMJHdXAzXI5",  # your TiDB password
        "database": "test",
        "use_pure": True,
        "connection_timeout": 15
    }
    
    import os
    if os.path.exists(ca_path):
        cnx_kwargs["ssl_ca"] = ca_path
        cnx_kwargs["ssl_verify_cert"] = True
    else:
        cnx_kwargs["ssl_disabled"] = False
        
    return mysql.connector.connect(**cnx_kwargs)
    
st.title("✂️ Salon & Barber Management ERP")

# Sidebar Navigation
menu = st.sidebar.radio(
    "Navigation Menu", 
    [
        "Book Appointment", 
        "Live Queue Desk", 
        "Appointment History", 
        "Financial Analytics", 
        "Manage Catalog & Staff"
    ]
)

conn = get_connection()
cursor = conn.cursor(dictionary=True)

# =========================================================
# MODULE 1: BOOK APPOINTMENT
# =========================================================
if menu == "Book Appointment":
    st.subheader("Book New Token / Appointment")
    
    cursor.execute("SELECT stylist_id, stylist_name FROM stylists")
    stylists = cursor.fetchall()
    
    cursor.execute("SELECT service_id, service_name, price, duration_mins FROM services")
    services = cursor.fetchall()
    
    col1, col2 = st.columns(2)
    with col1:
        cust_name = st.text_input("Customer Full Name")
        cust_phone = st.text_input("Mobile Number")
    
    with col2:
        stylist_choice = st.selectbox(
            "Select Stylist / Barber", 
            options=stylists, 
            format_func=lambda s: s["stylist_name"]
        )
        service_choice = st.selectbox(
            "Select Service", 
            options=services, 
            format_func=lambda x: f"{x['service_name']} (₹{x['price']} | {x['duration_mins']} mins)"
        )
    
    if st.button("Generate Token", type="primary"):
        if cust_name.strip() and cust_phone.strip():
            query = """
                INSERT INTO appointments (customer_name, customer_phone, stylist_id, service_id)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (
                cust_name.strip(), 
                cust_phone.strip(), 
                stylist_choice["stylist_id"], 
                service_choice["service_id"]
            ))
            conn.commit()
            st.success(f"Token #{cursor.lastrowid} booked for {cust_name}!")
        else:
            st.warning("Please enter both Customer Name and Mobile Number.")

# =========================================================
# MODULE 2: LIVE QUEUE DESK
# =========================================================
elif menu == "Live Queue Desk":
    st.subheader("Live Queue Status")
    
    query = """
        SELECT a.token_no, a.customer_name, a.customer_phone, 
               s.stylist_name, srv.service_name, srv.price, a.status, a.booking_time
        FROM appointments a
        JOIN stylists s ON a.stylist_id = s.stylist_id
        JOIN services srv ON a.service_id = srv.service_id
        WHERE a.status IN ('Waiting', 'In-Progress')
        ORDER BY a.token_no ASC
    """
    cursor.execute(query)
    queue_data = cursor.fetchall()
    
    if queue_data:
        df = pd.DataFrame(queue_data)
        st.dataframe(df, use_container_width=True)
        
        st.divider()
        st.markdown("#### Update Customer Status")
        col1, col2, col3 = st.columns(3)
        
        selected_token = col1.selectbox("Select Token #", df["token_no"].tolist())
        updated_status = col2.selectbox("Change Status To", ["In-Progress", "Completed", "Cancelled"])
        
        if col3.button("Update Status", type="primary"):
            update_sql = "UPDATE appointments SET status = %s WHERE token_no = %s"
            cursor.execute(update_sql, (updated_status, selected_token))
            conn.commit()
            st.success(f"Token #{selected_token} marked as '{updated_status}'")
            st.rerun()
    else:
        st.info("The live queue is currently clear.")

# =========================================================
# MODULE 3: APPOINTMENT HISTORY & SEARCH
# =========================================================
elif menu == "Appointment History":
    st.subheader("Audit Log & Appointment Records")
    
    col1, col2 = st.columns(2)
    phone_filter = col1.text_input("Filter by Phone Number")
    status_filter = col2.selectbox("Filter by Status", ["All", "Completed", "Cancelled", "Waiting", "In-Progress"])
    
    base_query = """
        SELECT a.token_no, a.customer_name, a.customer_phone, 
               s.stylist_name, srv.service_name, srv.price, a.status, a.booking_time
        FROM appointments a
        JOIN stylists s ON a.stylist_id = s.stylist_id
        JOIN services srv ON a.service_id = srv.service_id
        WHERE 1=1
    """
    params = []
    
    if phone_filter.strip():
        base_query += " AND a.customer_phone LIKE %s"
        params.append(f"%{phone_filter.strip()}%")
        
    if status_filter != "All":
        base_query += " AND a.status = %s"
        params.append(status_filter)
        
    base_query += " ORDER BY a.booking_time DESC"
    
    cursor.execute(base_query, tuple(params))
    history_records = cursor.fetchall()
    
    if history_records:
        history_df = pd.DataFrame(history_records)
        st.dataframe(history_df, use_container_width=True)
        
        # CSV Export Option
        csv_data = history_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export History to CSV",
            data=csv_data,
            file_name="salon_appointment_history.csv",
            mime="text/csv"
        )
    else:
        st.write("No matching appointment records found.")

# =========================================================
# MODULE 4: FINANCIAL ANALYTICS (DAY, MONTH, YEAR)
# =========================================================
elif menu == "Financial Analytics":
    st.subheader("Executive Financial & Performance Dashboard")
    
    # 1. Day / Month / Year Revenue Queries
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN DATE(a.booking_time) = CURDATE() THEN srv.price ELSE 0 END), 0) AS revenue_today,
            COALESCE(SUM(CASE WHEN MONTH(a.booking_time) = MONTH(CURDATE()) AND YEAR(a.booking_time) = YEAR(CURDATE()) THEN srv.price ELSE 0 END), 0) AS revenue_month,
            COALESCE(SUM(CASE WHEN YEAR(a.booking_time) = YEAR(CURDATE()) THEN srv.price ELSE 0 END), 0) AS revenue_year,
            COUNT(CASE WHEN a.status = 'Completed' THEN 1 END) AS total_completed
        FROM appointments a
        JOIN services srv ON a.service_id = srv.service_id
        WHERE a.status = 'Completed'
    """)
    rev_metrics = cursor.fetchone()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Revenue Today", f"₹ {rev_metrics['revenue_today']}")
    m2.metric("Revenue This Month", f"₹ {rev_metrics['revenue_month']}")
    m3.metric("Revenue This Year", f"₹ {rev_metrics['revenue_year']}")
    m4.metric("Total Completed", rev_metrics['total_completed'])
    
    st.divider()
    
    # Visual Analytics: Stylist breakdown & Top Services
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("#### Revenue by Stylist")
        cursor.execute("""
            SELECT s.stylist_name, SUM(srv.price) AS total_sales
            FROM appointments a
            JOIN stylists s ON a.stylist_id = s.stylist_id
            JOIN services srv ON a.service_id = srv.service_id
            WHERE a.status = 'Completed'
            GROUP BY s.stylist_name
        """)
        stylist_sales = cursor.fetchall()
        if stylist_sales:
            s_df = pd.DataFrame(stylist_sales)
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            ax1.bar(s_df["stylist_name"], s_df["total_sales"], color="#2563eb")
            ax1.set_ylabel("Revenue (₹)")
            st.pyplot(fig1)
        else:
            st.info("No completed services to display stylist breakdown.")

    with col_chart2:
        st.markdown("#### Most Popular Services")
        cursor.execute("""
            SELECT srv.service_name, COUNT(a.token_no) AS service_count
            FROM appointments a
            JOIN services srv ON a.service_id = srv.service_id
            WHERE a.status = 'Completed'
            GROUP BY srv.service_name
        """)
        service_counts = cursor.fetchall()
        if service_counts:
            srv_df = pd.DataFrame(service_counts)
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            ax2.pie(srv_df["service_count"], labels=srv_df["service_name"], autopct="%1.1f%%", startangle=90)
            st.pyplot(fig2)
        else:
            st.info("No completed services to display popular services chart.")

# =========================================================
# MODULE 5: MANAGE CATALOG & STAFF
# =========================================================
elif menu == "Manage Catalog & Staff":
    st.subheader("System Configuration")
    
    tab1, tab2 = st.tabs(["Add New Stylist", "Add New Service"])
    
    with tab1:
        with st.form("new_stylist_form"):
            new_stylist_name = st.text_input("Stylist / Barber Name")
            new_specialty = st.text_input("Specialty", placeholder="e.g. Skin Fade, Beard Grooming")
            if st.form_submit_button("Register Stylist"):
                if new_stylist_name.strip():
                    cursor.execute(
                        "INSERT INTO stylists (stylist_name, specialty) VALUES (%s, %s)",
                        (new_stylist_name.strip(), new_specialty.strip())
                    )
                    conn.commit()
                    st.success(f"Added {new_stylist_name} to stylists!")
                else:
                    st.warning("Stylist name cannot be empty.")
                    
    with tab2:
        with st.form("new_service_form"):
            new_service_name = st.text_input("Service Name")
            new_duration = st.number_input("Duration (in minutes)", min_value=5, max_value=240, step=5)
            new_price = st.number_input("Service Price (₹)", min_value=10.0, max_value=10000.0, step=50.0)
            if st.form_submit_button("Add Service"):
                if new_service_name.strip():
                    cursor.execute(
                        "INSERT INTO services (service_name, duration_mins, price) VALUES (%s, %s, %s)",
                        (new_service_name.strip(), int(new_duration), float(new_price))
                    )
                    conn.commit()
                    st.success(f"Added {new_service_name} to service menu!")
                else:
                    st.warning("Service name cannot be empty.")

cursor.close()
conn.close()
