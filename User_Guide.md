# Engineering Stores Management System (ESMS) - User Guide

Welcome to the Engineering Stores Management System (ESMS). This guide provides step-by-step instructions for all user roles on how to use the system to request, approve, issue, and track engineering materials efficiently.

---

## 1. Getting Started

### Accessing the System
1. Open your web browser and navigate to the ESMS portal.
2. Enter your assigned **Username** or **Email** and your **Password**.
3. Click **Sign In**.

### Password Reset Instructions
If you have forgotten your password:
1. On the login page, click the **Forgot Password?** link.
2. Enter your registered email address and click **Request Password Reset**.
3. Check your email inbox. You will receive an email containing a secure password reset link.
4. Click the link in the email. You will be securely redirected to a page where you can enter and confirm your new password.
5. Once submitted, you can log in immediately with your new password.

---

## 2. Employee Workflow (Requisition Generation)

Employees use ESMS to view available inventory and request materials.

### Creating a New Requisition
1. Log in to the system. You will land on your Employee Dashboard, which displays your request history.
2. Click **New Requisition** in the sidebar.
3. The system will display the current active inventory.
4. From the **Material Description** dropdown, select the material you need. The system will auto-fill the Material Code, UOM, Unit Rate, and Available Stock.
5. Enter the **Quantity Required**. *(Note: The quantity cannot exceed the available stock or be zero).*
6. Enter the **Cost Center** and **GL Code** if applicable to your department.
7. Provide an optional **Purpose / Remarks** to help approvers understand your request.
8. Click **Submit Requisition**. Your request will immediately be routed to the pending approval queue.

### Tracking Your Requests
* From your **Dashboard**, you can see the status of all your requests (`Pending Approval`, `Approved`, `Rejected`, or `Issued`).
* Click **View Details** on any request to see its full history, including who approved or rejected it and any remarks they left.

---

## 3. Approver Workflow

Approvers review pending requisitions and authorize them for issuance.

### Reviewing Pending Requests
1. Log in and navigate to the **Pending Approvals** page from the sidebar.
2. You will see a list of all requests waiting for your review. The table includes the employee name, material requested, total value, and submission date.
3. Click the **View** button next to a request to open its details.

### Approving or Rejecting
1. On the Request Details page, review the material, quantity, total amount, and any purpose remarks provided by the employee.
2. Add your own **Remarks** in the text box (optional for approvals, highly recommended for rejections).
3. Click the green **Approve** button to authorize the request, or the red **Reject** button to deny it.
4. **Note:** Once a request is approved, it automatically moves to the Store Manager's queue for issuance.

---

## 4. Store Manager Workflow

The Store Manager oversees daily inventory, physical stock issuance, and reporting.

### Inventory Upload Instructions
The Store Manager must upload the latest SAP inventory snapshot daily to keep the system synchronized.

1. Export the latest inventory from SAP as an Excel file (`.xlsx`).
2. Navigate to **Upload Inventory** in the sidebar.
3. Click **Choose File** and select the `.xlsx` file.
4. Click **Upload and Validate**.
5. The system will process the file, displaying a summary of valid items and any duplicates.
6. Once uploaded, this becomes the new "Active Inventory" that employees will see when requesting materials.

### Issuing Materials
1. Navigate to the **Issuance Queue** from the sidebar. This page lists all requests that have been explicitly approved by an Approver.
2. Locate the material physically in the store.
3. Once the material is ready to be handed to the employee, click **Issue Material** on the corresponding request in the system.
4. Add any optional remarks and click **Confirm Issue**.
5. The system records the transaction, stamps the current date and time, and marks the request as `Issued`.

---

## 5. Admin Workflow

Administrators manage user access, configure system settings, and oversee all operations.

### Managing Users
1. Navigate to **User Management** in the sidebar.
2. To add a new user, click **Add New User**. Fill in their details (Full Name, Username, Email, Employee ID, Department, and Role) and assign a temporary password.
3. To deactivate a user (e.g., if they leave the company), click the **Deactivate** button next to their name. Deactivated users cannot log into the system, but their historical requests and approvals are preserved.
4. To modify a user's role or department, click **Edit**.

### Auditing
* Navigate to **Audit Logs** to view a chronological history of critical system events, including inventory uploads, user logins, and administrative changes.

---

## 6. Report Generation

Both Store Managers and Administrators have access to the Reports module.

### Daily Issuance Report
1. Navigate to **Reports -> Daily Report**.
2. Select a specific date to view all materials issued on that day.
3. The report displays itemized costs, quantities, and totals.
4. Click **Export to Excel** to download the report for management review or financial reconciliation.

### Detailed Requisition Report
1. Navigate to **Reports -> Detailed Report**.
2. Use the advanced filters at the top of the page to narrow down data:
   * **Date Range:** Filter by specific start and end dates (defaults to the last 30 days).
   * **Status:** View all, or filter by Pending, Approved, Rejected, or Issued.
   * **Employee:** Search by name, Employee ID, or username.
   * **Material Code:** Search for specific materials.
3. The report will dynamically update, showing total requests, quantities, and approval/issuance details.
4. Click **Export to CSV** to download the exact filtered dataset for external analysis.

---

## 7. Common Troubleshooting Steps

**I forgot my password and am not receiving the reset email.**
* Check your spam or junk folder. Ensure that the email address you entered exactly matches the one registered in the system. If you still do not receive it, contact an Administrator to manually reset your password.

**I cannot submit a material request; the "Submit Requisition" button is disabled.**
* Ensure you have selected a valid material from the dropdown. 
* Ensure the "Quantity Required" is greater than zero and does not exceed the "Available Stock" shown on the screen. The button will automatically disable if the quantity is invalid.

**The inventory upload failed with an error message.**
* Ensure you are uploading a valid `.xlsx` Excel file.
* Ensure the Excel file contains the required columns: `Material`, `Material Description`, `BUn` (UOM), `UnR` (Unit Rate), and `Unrestricted` (Available Stock).

**I am seeing a "500 Internal Server Error".**
* This typically indicates a temporary server issue. Refresh the page. If the error persists, note down the exact steps you took before the error occurred and report it to the IT support team.
