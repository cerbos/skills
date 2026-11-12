# frozen_string_literal: true

class ApplicationController < ActionController::Base
  include Pundit::Authorization

  after_action :verify_authorized

  rescue_from Pundit::NotAuthorizedError do
    head :forbidden
  end

  def pundit_user
    Current.user
  end
end
