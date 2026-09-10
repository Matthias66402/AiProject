import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.jsx'
import HomePage from './pages/HomePage.jsx'
import JobsPage from './pages/JobsPage.jsx'
import JobEditPage from './pages/JobEditPage.jsx'
import CustomersPage from './pages/CustomersPage.jsx'
import CustomerEditPage from './pages/CustomerEditPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import UserEditPage from './pages/UserEditPage.jsx'
import ToolResumePage from './pages/ToolResumePage.jsx'
import ToolJobofferPage from './pages/ToolJobofferPage.jsx'
import MyResumesPage from './pages/MyResumesPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <BrowserRouter>
            <Routes>
                <Route path="/" element={<App />}>
                    <Route index element={<HomePage />} />
                    <Route path="jobs" element={<JobsPage />} />
                    <Route path="jobs/:jobId/edit" element={<JobEditPage />} />
                    <Route path="customers" element={<CustomersPage />} />
                    <Route
                        path="customers/:customerId/edit"
                        element={<CustomerEditPage />}
                    />
                    <Route path="users" element={<UsersPage />} />
                    <Route
                        path="users/:userId/edit"
                        element={<UserEditPage />}
                    />
                    <Route path="tools/resume" element={<ToolResumePage />} />
                    <Route
                        path="tools/joboffer"
                        element={<ToolJobofferPage />}
                    />
                    <Route path="resumes" element={<MyResumesPage />} />
                    <Route path="login" element={<LoginPage />} />
                    <Route path="register" element={<RegisterPage />} />
                </Route>
            </Routes>
        </BrowserRouter>
    </React.StrictMode>,
)
