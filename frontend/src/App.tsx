import { Navigate, Route, Routes } from "react-router";

import Header from "./components/layout/Header";
import LoginPage from "./features/auth/LoginPage";
import RequireAuth from "./features/auth/RequireAuth";
import SignupPage from "./features/auth/SignupPage";
import FriendsPage from "./features/friends/FriendsPage";
import HomePage from "./features/home/HomePage";
import InventoryPage from "./features/inventory/InventoryPage";
import ProfilePage from "./features/profile/ProfilePage";
import RoomDetailPage from "./features/rooms/RoomDetailPage";
import RoomsPage from "./features/rooms/RoomsPage";
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
          path="/amigos"
          element={
            <RequireAuth>
              <FriendsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/grupos"
          element={
            <RequireAuth>
              <RoomsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/grupos/:roomId"
          element={
            <RequireAuth>
              <RoomDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/inventario"
          element={
            <RequireAuth>
              <InventoryPage />
            </RequireAuth>
          }
        />
        <Route
          path="/inventario/:username"
          element={
            <RequireAuth>
              <InventoryPage />
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
