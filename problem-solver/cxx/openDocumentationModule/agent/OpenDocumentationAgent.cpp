#include "sc-agents-common/utils/AgentUtils.hpp"
#include "sc-agents-common/utils/CommonUtils.hpp"
#include "sc-agents-common/utils/IteratorUtils.hpp"
#include "sc-agents-common/keynodes/coreKeynodes.hpp"

#include "keynodes/OpenDocumentationKeynodes.hpp"
#include "OpenDocumentationAgent.hpp"

#include <cstdlib>
#include <fstream>
#include <mutex>
#include <string>

using namespace openDocumentationModule;
using namespace scAgentsCommon;

namespace
{
constexpr char const * URL_HANDOFF_PATH = "/home/nika/nika_cw/.last_open_documentation_url";
constexpr char const * OPENED_DOCUMENTATION_MARKER = "concept_message_with_opened_documentation";
}

SC_AGENT_IMPLEMENTATION(OpenDocumentationAgent)
{
  ScAddr const & actionAddr = otherAddr;
  if (!checkActionClass(actionAddr))
  {
    return SC_RESULT_OK;
  }

  SC_LOG_INFO("OpenDocumentationAgent started");

  ScAddr const & messageAddr =
      utils::IteratorUtils::getAnyByOutRelation(&m_memoryCtx, actionAddr, CoreKeynodes::rrel_1);
  if (!messageAddr.IsValid())
  {
    SC_LOG_ERROR("OpenDocumentationAgent: message address is not valid");
    utils::AgentUtils::finishAgentWork(&m_memoryCtx, actionAddr, false);
    return SC_RESULT_ERROR;
  }

  std::string name;
  try
  {
    messageSearcher = std::make_unique<dialogControlModule::MessageSearcher>(&m_memoryCtx);
    name = getMessageText(messageAddr);
  }
  catch (utils::ScException const & exception)
  {
    SC_LOG_ERROR("OpenDocumentationAgent: " << exception.Description());
    utils::AgentUtils::finishAgentWork(&m_memoryCtx, actionAddr, false);
    return SC_RESULT_ERROR;
  }

  SC_LOG_INFO("OpenDocumentationAgent: message text = " << name);

  std::string const url =
      "https://www.linkedin.com/in/viktoryia-kavalchuk-0b4349361/?isSelfProfile=false";
  SC_LOG_INFO("OpenDocumentationAgent: open url " << url);

  // The knowledge base can trigger the same action for the same message more than once.
  // Remember messages that already opened the URL so they are not reopened in a loop.
  bool shouldOpen = true;
  {
    static std::mutex openDocumentationMutex;
    std::lock_guard<std::mutex> lock(openDocumentationMutex);

    ScAddr const & markerClass =
        m_memoryCtx.HelperResolveSystemIdtf(OPENED_DOCUMENTATION_MARKER, ScType::NodeConstClass);

    if (m_memoryCtx.HelperCheckEdge(markerClass, messageAddr, ScType::EdgeAccessConstPosPerm))
    {
      shouldOpen = false;
    }
    else
    {
      std::ofstream urlFile(URL_HANDOFF_PATH, std::ios::trunc);
      if (urlFile)
      {
        urlFile << url << '\n';
      }
      else
      {
        SC_LOG_WARNING("OpenDocumentationAgent: cannot write " << URL_HANDOFF_PATH);
      }

      m_memoryCtx.CreateEdge(ScType::EdgeAccessConstPosPerm, markerClass, messageAddr);
    }
  }

  if (shouldOpen)
  {
    (void)std::system(("xdg-open \"" + url + "\" >/dev/null 2>&1 || true").c_str());
    SC_LOG_INFO("OpenDocumentationAgent finished");
  }
  else
  {
    SC_LOG_INFO("OpenDocumentationAgent: url is already opened for this message, skipping");
  }

  utils::AgentUtils::finishAgentWork(&m_memoryCtx, actionAddr, true);
  return SC_RESULT_OK;
}

bool OpenDocumentationAgent::checkActionClass(ScAddr const & actionAddr)
{
  return m_memoryCtx.HelperCheckEdge(
      OpenDocumentationKeynodes::action_open_documentation, actionAddr, ScType::EdgeAccessConstPosPerm);
}

std::string OpenDocumentationAgent::getMessageText(ScAddr const & messageAddr)
{
  ScAddr const & messageLink = messageSearcher->getMessageLink(messageAddr);
  if (!messageLink.IsValid())
  {
    SC_THROW_EXCEPTION(utils::ExceptionItemNotFound, "OpenDocumentationAgent: message link is not found.");
  }
  return utils::CommonUtils::getLinkContent(&m_memoryCtx, messageLink);
}
