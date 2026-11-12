# frozen_string_literal: true

class ApplicationPolicy
  attr_reader :user, :record

  def initialize(user, record)
    raise Pundit::NotAuthorizedError, "account suspended" if user&.suspended?

    @user = user
    @record = record
  end

  def index?
    false
  end

  def show?
    false
  end

  def create?
    false
  end

  def new?
    create?
  end

  def update?
    false
  end

  def edit?
    update?
  end

  def destroy?
    false
  end

  private

  def admin?
    user.present? && user.roles.include?("admin")
  end

  def member_of?(team_id)
    user.present? && user.team_ids.include?(team_id)
  end
end
