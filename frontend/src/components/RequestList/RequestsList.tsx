import RequestCard from "../RequestCard/RequestCard";
import styles from './RequestsList.module.css'

const RequestsList = () => {
    return <div className={styles.requestsList}>
    <RequestCard request="Возраст всех мужских персонажей мультсериала рик и морти" time="12:00"/></div>
}

export default RequestsList;
