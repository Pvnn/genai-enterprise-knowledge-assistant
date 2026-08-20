/**
 * MembersTab Component for Admin Dashboard.
 * Manage enterprise members, invite users, update administrative roles, and manage permissions.
 */

import React, { useState } from "react";
import {
  Users,
  UserPlus,
  ShieldCheck,
  User,
  Trash,
  MagnifyingGlass,
  CheckCircle,
  WarningCircle,
  CircleNotch,
  ArrowClockwise,
  Key,
  EnvelopeSimple,
  X,
} from "@phosphor-icons/react";
import { AdminUser } from "../types";

interface MembersTabProps {
  users: AdminUser[];
  currentUserId?: string;
  loading: boolean;
  onRefresh: () => void;
  onCreateUser: (data: { email: string; password: string; role: string }) => Promise<void>;
  onUpdateUserRole: (userId: string, role: string) => Promise<void>;
  onDeleteUser: (userId: string) => Promise<void>;
}

export const MembersTab: React.FC<MembersTabProps> = ({
  users,
  currentUserId,
  loading,
  onRefresh,
  onCreateUser,
  onUpdateUserRole,
  onDeleteUser,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | "admin" | "member">("all");
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false);
  const [confirmDeleteUser, setConfirmDeleteUser] = useState<AdminUser | null>(null);

  // New user form state
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("member");
  const [formError, setFormError] = useState<string | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);

  // Action loading states
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);

  const adminCount = users.filter((u) => u.role === "admin").length;
  const memberCount = users.filter((u) => u.role === "member").length;

  const filteredUsers = users.filter((u) => {
    const matchesEmail = u.email.toLowerCase().includes(searchQuery.toLowerCase());
    if (roleFilter === "admin") return matchesEmail && u.role === "admin";
    if (roleFilter === "member") return matchesEmail && u.role === "member";
    return matchesEmail;
  });

  const handleRoleChange = async (user: AdminUser, newRole: string) => {
    if (user.role === newRole) return;
    setUpdatingUserId(user.id);
    try {
      await onUpdateUserRole(user.id, newRole);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to update role");
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim() || !newPassword.trim()) {
      setFormError("Email and temporary password are required.");
      return;
    }
    setFormSubmitting(true);
    setFormError(null);

    try {
      await onCreateUser({
        email: newEmail.trim(),
        password: newPassword.trim(),
        role: newRole,
      });
      setIsAddUserModalOpen(false);
      setNewEmail("");
      setNewPassword("");
      setNewRole("member");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!confirmDeleteUser) return;
    setDeletingUserId(confirmDeleteUser.id);
    try {
      await onDeleteUser(confirmDeleteUser.id);
      setConfirmDeleteUser(null);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete user");
    } finally {
      setDeletingUserId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Total Enterprise Members
            </span>
            <div className="w-8 h-8 rounded-xl bg-primary-brand/10 text-primary-brand flex items-center justify-center">
              <Users size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-ink tracking-tight">
            {users.length}
          </div>
          <p className="text-[11px] text-ink-muted mt-1">Authorized knowledge base users</p>
        </div>

        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Administrators
            </span>
            <div className="w-8 h-8 rounded-xl bg-accent-gold/15 text-accent-gold flex items-center justify-center">
              <ShieldCheck size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-ink tracking-tight">
            {adminCount}
          </div>
          <p className="text-[11px] text-ink-muted mt-1">Can upload docs & manage organization</p>
        </div>

        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Standard Members
            </span>
            <div className="w-8 h-8 rounded-xl bg-slate-500/10 text-slate-600 dark:text-slate-400 flex items-center justify-center">
              <User size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-2 text-2xl font-bold text-ink tracking-tight">
            {memberCount}
          </div>
          <p className="text-[11px] text-ink-muted mt-1">Grounded policy query access</p>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <MagnifyingGlass
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted"
          />
          <input
            type="text"
            placeholder="Search members by email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink placeholder:text-ink-muted focus:outline-none focus:border-primary-brand"
          />
        </div>

        {/* Filters and Add Action */}
        <div className="flex items-center gap-2">
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as "all" | "admin" | "member")}
            className="py-2 px-3 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
          >
            <option value="all">All Roles</option>
            <option value="admin">Admins Only</option>
            <option value="member">Members Only</option>
          </select>

          <button
            type="button"
            onClick={onRefresh}
            className="p-2 rounded-xl border border-hairline text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
            title="Refresh member list"
          >
            <ArrowClockwise size={15} />
          </button>

          <button
            type="button"
            onClick={() => setIsAddUserModalOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-primary-brand hover:bg-primary-brand-hover text-white shadow-2xs transition-all active:scale-[0.98]"
          >
            <UserPlus size={14} weight="bold" />
            <span>Invite Member</span>
          </button>
        </div>
      </div>

      {/* Members Data Table */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-ink tracking-tight">
            Organization Directory
          </h3>
          <span className="text-xs font-mono text-ink-muted">
            {filteredUsers.length} of {users.length} members
          </span>
        </div>

        {loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-ink-muted gap-2">
            <CircleNotch size={24} className="animate-spin text-primary-brand" />
            <span className="text-xs">Loading members...</span>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-12 text-center rounded-2xl bg-surface-muted/30 border border-hairline space-y-2">
            <Users size={32} className="mx-auto text-ink-muted/50" />
            <p className="text-xs font-medium text-ink">No members found</p>
            <p className="text-[11px] text-ink-muted">
              Try adjusting your search filter or invite a new member.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-hairline text-ink-muted font-semibold">
                  <th className="pb-3 px-3">Member Email</th>
                  <th className="pb-3 px-3">Access Role</th>
                  <th className="pb-3 px-3">User ID</th>
                  <th className="pb-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {filteredUsers.map((user) => {
                  const isAdmin = user.role === "admin";
                  const isSelf = user.id === currentUserId;

                  return (
                    <tr key={user.id} className="hover:bg-surface-muted/40 transition-colors">
                      <td className="py-3 px-3 font-medium text-ink">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-surface border border-hairline flex items-center justify-center text-ink-muted">
                            {isAdmin ? (
                              <ShieldCheck size={15} className="text-accent-gold" weight="bold" />
                            ) : (
                              <User size={15} />
                            )}
                          </div>
                          <span>{user.email}</span>
                          {isSelf && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-primary-brand/10 text-primary-brand font-semibold font-mono">
                              You
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-3">
                        <select
                          value={user.role}
                          disabled={updatingUserId === user.id || (isSelf && isAdmin)}
                          onChange={(e) => handleRoleChange(user, e.target.value)}
                          className={`py-1 px-2.5 rounded-xl text-xs font-semibold border transition-all focus:outline-none ${
                            isAdmin
                              ? "bg-accent-gold/10 text-accent-gold border-accent-gold/30"
                              : "bg-surface-muted text-ink-muted border-hairline"
                          } disabled:opacity-60 cursor-pointer`}
                        >
                          <option value="member">Member</option>
                          <option value="admin">Administrator</option>
                        </select>
                      </td>

                      <td className="py-3 px-3 font-mono text-[11px] text-ink-muted select-all">
                        {user.id}
                      </td>

                      <td className="py-3 px-3 text-right">
                        <button
                          type="button"
                          disabled={isSelf}
                          onClick={() => setConfirmDeleteUser(user)}
                          title={isSelf ? "Cannot delete your own account" : "Remove user"}
                          className="p-1.5 rounded-lg text-ink-muted hover:text-rose-500 hover:bg-rose-500/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <Trash size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Invite Member Modal */}
      {isAddUserModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-md bg-surface border border-hairline rounded-3xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-hairline pb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-primary-brand text-white flex items-center justify-center">
                  <UserPlus size={16} weight="bold" />
                </div>
                <h3 className="text-sm font-bold text-ink">Invite Enterprise Member</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsAddUserModalOpen(false)}
                className="p-1 text-ink-muted hover:text-ink"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-3 text-xs">
              {formError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 text-xs">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                  Email Address
                </label>
                <div className="relative">
                  <EnvelopeSimple size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
                  <input
                    type="email"
                    required
                    placeholder="colleague@enterprise.com"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="w-full pl-8 pr-3 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                  Temporary Password
                </label>
                <div className="relative">
                  <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
                  <input
                    type="password"
                    required
                    placeholder="Enter password..."
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full pl-8 pr-3 py-2 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-ink-muted mb-1">
                  Initial Role
                </label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full py-2 px-3 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
                >
                  <option value="member">Standard Member (Query only)</option>
                  <option value="admin">Administrator (Upload & manage)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-hairline">
                <button
                  type="button"
                  onClick={() => setIsAddUserModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="px-4 py-2 text-xs font-semibold rounded-xl bg-primary-brand text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
                >
                  {formSubmitting ? (
                    <>
                      <CircleNotch size={13} className="animate-spin" />
                      <span>Creating...</span>
                    </>
                  ) : (
                    <span>Create User</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete User Confirmation */}
      {confirmDeleteUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-sm bg-surface border border-hairline rounded-3xl p-6 shadow-xl space-y-4">
            <div className="w-10 h-10 rounded-2xl bg-rose-500/10 text-rose-500 flex items-center justify-center">
              <Trash size={20} weight="bold" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-ink">Remove Enterprise Member</h3>
              <p className="text-xs text-ink-muted mt-1">
                Are you sure you want to revoke access for <strong className="text-ink">{confirmDeleteUser.email}</strong>? They will no longer be able to log in.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteUser(null)}
                className="px-4 py-2 text-xs font-medium rounded-xl bg-surface border border-hairline text-ink hover:bg-surface-muted transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deletingUserId === confirmDeleteUser.id}
                onClick={handleDeleteConfirm}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-rose-600 hover:bg-rose-700 text-white transition-all disabled:opacity-50 flex items-center gap-1.5"
              >
                {deletingUserId === confirmDeleteUser.id ? (
                  <>
                    <CircleNotch size={13} className="animate-spin" />
                    <span>Removing...</span>
                  </>
                ) : (
                  <span>Remove Access</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MembersTab;
