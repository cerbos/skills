# frozen_string_literal: true

class DocumentPolicy < ApplicationPolicy
  def show?
    return true if admin?
    return false if external? && record.confidential
    return true if record.published
    return false if user.nil?

    owner? || member_of?(record.team_id)
  end

  def create?
    user.present? && (user.roles & %w[editor admin]).any?
  end

  def update?
    return true if admin?
    return false if locked_by_someone_else?

    owner? || (editor? && member_of?(record.team_id))
  end

  alias_method :publish?, :update?

  def destroy?
    admin? || (owner? && !record.published)
  end

  private

  def owner?
    user.present? && record.owner_id == user.id
  end

  def editor?
    user.present? && user.roles.include?("editor")
  end

  def external?
    user.present? && user.roles.include?("external")
  end

  def locked_by_someone_else?
    record.locked_by.present? && record.locked_by != user&.id
  end
end
