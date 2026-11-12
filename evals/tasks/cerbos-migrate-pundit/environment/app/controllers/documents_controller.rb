# frozen_string_literal: true

class DocumentsController < ApplicationController
  before_action :set_document, only: %i[show edit update publish destroy]

  def show
    authorize @document
  end

  def new
    @document = authorize Document.new
  end

  def create
    @document = authorize Document.new(document_params.merge(owner_id: current_user.id))
    @document.save!
    redirect_to @document
  end

  def edit
    authorize @document
  end

  def update
    authorize @document
    @document.update!(document_params)
    redirect_to @document
  end

  def publish
    authorize @document
    @document.update!(published: true)
    redirect_to @document
  end

  def destroy
    authorize @document
    @document.destroy!
    redirect_to documents_path
  end

  private

  def set_document
    @document = Document.find(params[:id])
  end

  def document_params
    params.expect(document: %i[title body team_id confidential])
  end
end
