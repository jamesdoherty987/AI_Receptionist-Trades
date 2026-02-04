# Final Production Test Plan

## 🚀 Quick Test Sequence

Run these tests in order to verify everything works:

### 1. Backend Health Check
```bash
curl https://ai-receptionist-backend-0e9i.onrender.com/health
# Expected: {"status": "healthy"}
```

### 2. Database Connection Test
Open your backend logs on Render and look for:
- ✅ "🐘 PostgreSQL connection pool created"
- ✅ "✅ Connected to PostgreSQL"
- ❌ NO "⚠️ Error" messages

### 3. Frontend Load Test
Visit: https://ai-receptionist-trades-9y7n.vercel.app/
- ✅ Landing page loads
- ✅ No console errors (F12 → Console)

### 4. User Signup Flow
1. Go to: https://ai-receptionist-trades-9y7n.vercel.app/signup
2. Fill in:
   - Company Name: Test Plumbing Co
   - Your Name: John Test
   - Email: test+[random]@gmail.com (use unique email)
   - Phone: +353 86 123 4567
   - Trade Type: Plumbing
   - Password: TestPass123!
3. Click "Create Account"
4. ✅ Should redirect to dashboard
5. ✅ Should see empty bookings/clients/workers

### 5. User Login Flow
1. Logout (top right)
2. Go to: https://ai-receptionist-trades-9y7n.vercel.app/login
3. Login with the same email/password
4. ✅ Should redirect to dashboard
5. ✅ Should still show your company name

### 6. Client Creation Test
1. In dashboard, go to "Customers" tab
2. Click "Add New Customer"
3. Fill in:
   - Name: Test Customer
   - Phone: +353 86 999 1234
   - Email: customer@test.com
   - Address: 123 Test St, Dublin
4. Click "Add Customer"
5. ✅ Should see new customer in list
6. ✅ Check backend logs for: "✅ Client added with ID: X"

### 7. Booking Creation Test
1. Go to "Jobs" tab
2. Click "Add New Job"
3. Fill in:
   - Customer: Select "Test Customer" from dropdown
   - Service: Plumbing Repair
   - Date/Time: Tomorrow at 2:00 PM
   - Address: 123 Test St, Dublin
   - Charge: 150
4. Click "Add Job"
5. ✅ Should see new booking in calendar
6. ✅ Check backend logs for: "✅ Booking added with ID: X"

### 8. Booking Update Test
1. Click on the booking you just created
2. Change:
   - Status: In Progress
   - Notes: "Test note added"
   - Charge: 175
3. Click "Save"
4. ✅ Should see updated values
5. ✅ Refresh page - values should persist

### 9. Worker Management Test
1. Go to "Workers" tab
2. Click "Add New Worker"
3. Fill in:
   - Name: Test Worker
   - Role: Plumber
   - Phone: +353 86 777 5555
   - Email: worker@test.com
4. Click "Add Worker"
5. ✅ Should see new worker in list

### 10. Financial Stats Test
1. Go to "Finances" tab
2. ✅ Should see:
   - Total Revenue (should include the €175 booking)
   - Revenue This Month
   - Recent Transactions
3. ✅ Check backend logs for: "💰 Finance stats calculated"

---

## 🔍 Backend Logs to Monitor

### Good Signs ✅:
```
✅ Connected to PostgreSQL
🐘 PostgreSQL connection pool created
✅ Company created with ID: X
✅ Client added with ID: X
✅ Booking added with ID: X
💰 Finance stats calculated
```

### Bad Signs ❌:
```
❌ Error creating company
❌ PostgreSQL wrapper error
⚠️ Method not implemented
syntax error at or near "?"
relation "X" does not exist
```

---

## 📊 Database Verification

If you have psql access, run these queries:

```sql
-- Check companies
SELECT id, name, email, created_at FROM companies ORDER BY created_at DESC LIMIT 5;

-- Check clients
SELECT id, name, phone, email, created_at FROM clients ORDER BY created_at DESC LIMIT 5;

-- Check bookings
SELECT id, client_id, service_type, appointment_time, charge, status 
FROM bookings 
ORDER BY created_at DESC 
LIMIT 5;

-- Check workers
SELECT id, name, role, phone FROM workers ORDER BY created_at DESC LIMIT 5;

-- Verify no SQLite artifacts
\d bookings
-- Should show PostgreSQL types (timestamp, real, text) not SQLite types
```

---

## 🐛 Common Issues & Fixes

### Issue: "Error creating company"
**Fix:** Check DATABASE_URL in Render environment variables
```bash
# Should look like:
postgresql://username:password@hostname:5432/dbname
```

### Issue: "syntax error at or near ?"
**Fix:** This shouldn't happen anymore, but if it does:
1. Grep for `?` in SQL queries: `grep -r "cursor.execute.*?" src/`
2. Replace with `%s`

### Issue: "Method not implemented"
**Fix:** Check if method exists in PostgreSQL wrapper
```bash
grep "def method_name" src/services/db_postgres_wrapper.py
```

### Issue: "Import psycopg2 could not be resolved"
**Fix:** This is LOCAL dev only. Production (Render) has psycopg2-binary installed via requirements.txt

### Issue: Frontend shows "Network Error"
**Fix:** Check CORS settings in backend:
```python
# In app.py
CORS(app, supports_credentials=True, origins=[
    "https://ai-receptionist-trades-9y7n.vercel.app",
    "http://localhost:5173"
])
```

---

## ✅ Success Criteria

All tests pass when:
- [x] Health endpoint returns 200
- [x] User can signup
- [x] User can login
- [x] User can create clients
- [x] User can create bookings
- [x] User can update bookings
- [x] User can add workers
- [x] Financial stats load
- [x] No "syntax error" in logs
- [x] No "Method not implemented" errors
- [x] Data persists after page refresh

---

## 📝 Next Steps After Testing

1. **Set up monitoring:**
   - Sentry for error tracking
   - LogRocket for session replay
   - Render metrics for performance

2. **Configure backups:**
   - Enable daily PostgreSQL backups in Render
   - Export config files to secure location

3. **Security hardening:**
   - Rotate JWT secret
   - Enable rate limiting
   - Add request validation

4. **Documentation:**
   - API documentation (Swagger/OpenAPI)
   - User guide for dashboard
   - Webhook documentation for Twilio

5. **Performance optimization:**
   - Add database indexes
   - Enable query caching
   - Optimize frontend bundle size

---

**Ready to test!** Start with step 1 and work your way down. Report any errors immediately.
