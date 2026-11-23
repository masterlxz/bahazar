import { Navigate, Route, Routes } from "react-router";

import Header from "./components/layout/Header";
import LoginPage from "./features/auth/LoginPage";
import RequireAuth from "./features/auth/RequireAuth";
import SignupPage from "./features/auth/SignupPage";
import HomePage from "./features/home/HomePage";
import ProfilePage from "./features/profile/ProfilePage";
import WalletPage from "./features/wallet/WalletPage";

export default function App() {
  return (
    <>
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/entrar" element={<LoginPage />} />
        <Route path="/cadastrar" element={<SignupPage />} />
        <Route
          path="/perfil"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
        <Route
          path="/carteira"
          element={
            <RequireAuth>
              <WalletPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
