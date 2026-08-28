import React, { useState, useEffect, useCallback } from "react";
import { UserItem, listUsers, createUser, updateUser, resetUserPassword } from "../api/users";
import { UserRole } from "../types/auth";
import { Users, UserPlus, Shield, KeyRound, CheckCircle, XCircle, AlertTriangle, RefreshCw } from "lucide-react";

export function UsersPage() {
  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newUsername, setNewUsername] = useState<string>("");
  const [newDisplayName, setNewDisplayName] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [newRole, setNewRole] = useState<UserRole>("OPERATOR");
  const [createError, setCreateError] = useState<string | null>(null);

  const [resetTargetUser, setResetTargetUser] = useState<UserItem | null>(null);
  const [resetPasswordVal, setResetPasswordVal] = useState<string>("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listUsers({ limit: 100 });
      setUsers(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setError(err.message || "Failed to load user administration list.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    try {
      await createUser({
        username: newUsername,
        display_name: newDisplayName,
        password: newPassword,
        role: newRole,
        must_change_password: true,
      });
      setShowCreateModal(false);
      setNewUsername("");
      setNewDisplayName("");
      setNewPassword("");
      setNewRole("OPERATOR");
      fetchUsers();
    } catch (err: any) {
      setCreateError(err.message || "Failed to create user.");
    }
  };

  const handleToggleEnabled = async (user: UserItem) => {
    try {
      await updateUser(user.user_id, { enabled: !user.enabled });
      fetchUsers();
    } catch (err: any) {
      alert(err.message || "Failed to update user status.");
    }
  };

  const handleRoleChange = async (user: UserItem, newRoleVal: UserRole) => {
    try {
      await updateUser(user.user_id, { role: newRoleVal });
      fetchUsers();
    } catch (err: any) {
      alert(err.message || "Failed to update user role.");
    }
  };

  const handleResetPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetTargetUser) return;
    setResetError(null);
    setResetSuccess(null);
    try {
      await resetUserPassword(resetTargetUser.user_id, resetPasswordVal);
      setResetSuccess(`Password reset successfully for ${resetTargetUser.username}.`);
      setResetPasswordVal("");
      setTimeout(() => {
        setResetTargetUser(null);
        setResetSuccess(null);
      }, 2000);
    } catch (err: any) {
      setResetError(err.message || "Failed to reset password.");
    }
  };

  const getRoleBadge = (role: UserRole) => {
    switch (role) {
      case "ADMIN":
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-purple-950 text-purple-300 border border-purple-700">ADMIN</span>;
      case "SUPERVISOR":
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-950 text-blue-300 border border-blue-700">SUPERVISOR</span>;
      case "OPERATOR":
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-700">OPERATOR</span>;
      case "AUDITOR":
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-950 text-amber-300 border border-amber-700">AUDITOR</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-xs font-bold bg-slate-800 text-slate-300 border border-slate-700">{role}</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-police-850 p-4 rounded-lg border border-police-750">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-accent-blue/10 border border-accent-blue/40 text-accent-blue">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-wide text-white font-mono">USER ADMINISTRATION</h1>
            <p className="text-xs text-slate-400">Manage authenticated operators, supervisors, and role assignments</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchUsers}
            disabled={loading}
            className="p-2 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 transition-colors"
            title="Refresh Users"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent-blue hover:bg-accent-blue-hover text-white text-xs font-semibold tracking-wide font-mono transition-colors shadow-md shadow-accent-blue/20"
          >
            <UserPlus className="w-4 h-4" />
            <span>CREATE USER</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-rose-950/80 border border-rose-700 rounded-lg text-xs text-rose-200 flex items-center gap-2 font-mono">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Users Table */}
      <div className="bg-police-850 rounded-lg border border-police-750 overflow-hidden shadow-lg">
        <div className="px-4 py-2.5 bg-police-800/80 border-b border-police-750 flex items-center justify-between text-xs font-mono text-slate-400">
          <span>ACTIVE OPERATOR ACCOUNTS ({total})</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-police-800/40 text-slate-400 border-b border-police-750">
              <tr>
                <th className="p-3">USERNAME</th>
                <th className="p-3">DISPLAY NAME</th>
                <th className="p-3">ROLE</th>
                <th className="p-3">STATUS</th>
                <th className="p-3">LAST LOGIN</th>
                <th className="p-3 text-right">ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-police-750/60 text-slate-200">
              {users.map((u) => (
                <tr key={u.user_id} className="hover:bg-police-800/30 transition-colors">
                  <td className="p-3 font-semibold text-cyan-300">{u.username}</td>
                  <td className="p-3">{u.display_name}</td>
                  <td className="p-3">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
                      className="bg-police-800 border border-police-700 rounded px-2 py-1 text-xs text-slate-200 font-mono cursor-pointer"
                    >
                      <option value="ADMIN">ADMIN</option>
                      <option value="SUPERVISOR">SUPERVISOR</option>
                      <option value="OPERATOR">OPERATOR</option>
                      <option value="AUDITOR">AUDITOR</option>
                    </select>
                  </td>
                  <td className="p-3">
                    {u.enabled ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
                        <CheckCircle className="w-3.5 h-3.5" /> Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-rose-400 text-xs">
                        <XCircle className="w-3.5 h-3.5" /> Disabled
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-slate-400 text-[11px]">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                  </td>
                  <td className="p-3 text-right space-x-2">
                    <button
                      onClick={() => setResetTargetUser(u)}
                      className="px-2.5 py-1 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 hover:text-white text-xs inline-flex items-center gap-1 transition-colors"
                      title="Reset User Password"
                    >
                      <KeyRound className="w-3 h-3 text-amber-400" />
                      <span>Reset Pwd</span>
                    </button>
                    <button
                      onClick={() => handleToggleEnabled(u)}
                      className={`px-2.5 py-1 rounded border text-xs font-semibold transition-colors ${
                        u.enabled
                          ? "bg-rose-950/60 hover:bg-rose-900 border-rose-700 text-rose-300"
                          : "bg-emerald-950/60 hover:bg-emerald-900 border-emerald-700 text-emerald-300"
                      }`}
                    >
                      {u.enabled ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-slate-500 font-mono">
                    No operator accounts configured.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-police-850 border border-police-700 rounded-lg max-w-md w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-police-750 pb-3">
              <div className="flex items-center gap-2 text-white font-mono font-bold text-sm">
                <UserPlus className="w-4 h-4 text-accent-blue" />
                <span>CREATE OPERATOR ACCOUNT</span>
              </div>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white font-mono text-sm"
              >
                ✕
              </button>
            </div>

            {createError && (
              <div className="p-2.5 bg-rose-950/80 border border-rose-700 rounded text-xs text-rose-200 font-mono">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateUser} className="space-y-3 font-mono text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Username (normalized lowercase)</label>
                <input
                  type="text"
                  required
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="e.g. operator_ahmedabad"
                  className="w-full bg-police-900 border border-police-700 rounded p-2 text-slate-100 focus:outline-hidden focus:border-accent-blue"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Display Name</label>
                <input
                  type="text"
                  required
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                  placeholder="e.g. Officer R. Sharma"
                  className="w-full bg-police-900 border border-police-700 rounded p-2 text-slate-100 focus:outline-hidden focus:border-accent-blue"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Initial Password (min 15 characters)</label>
                <input
                  type="password"
                  required
                  minLength={15}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 15 characters long"
                  className="w-full bg-police-900 border border-police-700 rounded p-2 text-slate-100 focus:outline-hidden focus:border-accent-blue"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Assigned Role</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as UserRole)}
                  className="w-full bg-police-900 border border-police-700 rounded p-2 text-slate-100 focus:outline-hidden focus:border-accent-blue cursor-pointer"
                >
                  <option value="OPERATOR">OPERATOR (View alerts, CCTV streams, ACK alerts)</option>
                  <option value="SUPERVISOR">SUPERVISOR (Target watchlist management + ACK)</option>
                  <option value="AUDITOR">AUDITOR (Read-only forensics and audit trail inspection)</option>
                  <option value="ADMIN">ADMIN (Full system, user management, and configuration)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-police-750">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-accent-blue hover:bg-accent-blue-hover text-white font-semibold shadow"
                >
                  Create Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {resetTargetUser && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-police-850 border border-police-700 rounded-lg max-w-md w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-police-750 pb-3">
              <div className="flex items-center gap-2 text-white font-mono font-bold text-sm">
                <KeyRound className="w-4 h-4 text-amber-400" />
                <span>RESET PASSWORD: {resetTargetUser.username}</span>
              </div>
              <button
                onClick={() => setResetTargetUser(null)}
                className="text-slate-400 hover:text-white font-mono text-sm"
              >
                ✕
              </button>
            </div>

            {resetError && (
              <div className="p-2.5 bg-rose-950/80 border border-rose-700 rounded text-xs text-rose-200 font-mono">
                {resetError}
              </div>
            )}

            {resetSuccess && (
              <div className="p-2.5 bg-emerald-950/80 border border-emerald-700 rounded text-xs text-emerald-200 font-mono">
                {resetSuccess}
              </div>
            )}

            <form onSubmit={handleResetPasswordSubmit} className="space-y-3 font-mono text-xs">
              <div>
                <label className="block text-slate-300 mb-1">New Password (min 15 characters)</label>
                <input
                  type="password"
                  required
                  minLength={15}
                  value={resetPasswordVal}
                  onChange={(e) => setResetPasswordVal(e.target.value)}
                  placeholder="Enter new 15+ char passphrase"
                  className="w-full bg-police-900 border border-police-700 rounded p-2 text-slate-100 focus:outline-hidden focus:border-accent-blue"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-police-750">
                <button
                  type="button"
                  onClick={() => setResetTargetUser(null)}
                  className="px-3 py-1.5 rounded bg-police-800 hover:bg-police-700 border border-police-700 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-amber-600 hover:bg-amber-500 text-white font-semibold shadow"
                >
                  Apply Password Reset
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
