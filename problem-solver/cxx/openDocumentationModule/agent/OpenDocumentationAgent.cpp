#include "sc-agents-common/utils/AgentUtils.hpp"
#include "sc-agents-common/utils/CommonUtils.hpp"
#include "sc-agents-common/utils/IteratorUtils.hpp"
#include "sc-agents-common/keynodes/coreKeynodes.hpp"

#include "keynodes/OpenDocumentationKeynodes.hpp"
#include "OpenDocumentationAgent.hpp"

#include <cstdlib>
#include <fstream>
#include <string>

using namespace openDocumentationModule;
using namespace scAgentsCommon;

namespace
{
constexpr char const * URL_HANDOFF_PATH = "/home/nika/nika_cw/.last_open_documentation_url";
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
  }


  (void)std::system(("xdg-open \"" + url + "\" >/dev/null 2>&1 || true").c_str());

  utils::AgentUtils::finishAgentWork(&m_memoryCtx, actionAddr, true);
  SC_LOG_INFO("OpenDocumentationAgent finished");
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
